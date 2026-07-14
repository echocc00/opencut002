"""TTS Agent - 逐段生成配音 + 精确段落时间戳

成熟做法：TTS 本身是时间源头。每段文案单独 TTS，ffprobe 取精确时长，
concat 拼接成完整音频。段落时长精确 -> 一段一画面、不丢句、不切句。
不再依赖转录（WhisperX/fallback）反推时间（转录会丢字符、边界不准）。
"""
from __future__ import annotations
import logging
import subprocess
import json
from typing import Any
from ..orchestrator.state import ProjectState, StageState
from ..providers.selector import TaskType
from ..tools.tts_generator import generate_tts
from .base_agent import BaseStageAgent

log = logging.getLogger(__name__)


def _probe_duration(path: str) -> float:
    """ffprobe 取音频时长"""
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "json", path],
        capture_output=True, text=True, timeout=15,
    )
    return float(json.loads(r.stdout)["format"]["duration"])


def _concat_audio(seg_paths: list[str], output: str) -> None:
    """ffmpeg concat 拼接分段音频"""
    import os
    list_file = output + ".list"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in seg_paths:
            # 用绝对路径（concat demuxer 按 list 文件目录解析相对路径，会翻倍）
            abs_p = os.path.abspath(p).replace("\\", "/")
            f.write(f"file '{abs_p}'\n")
    # 重新编码避免不同 mp3 参数拼接失败
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
         "-c:a", "libmp3lame", "-b:a", "128k", output],
        capture_output=True, timeout=180, check=True,
    )
    os.remove(list_file)


# 文案 emotion_tone 描述 -> minimax TTS emotion 取值
# minimax 支持: happy/sad/angry/fearful/disgusted/surprised/neutral
EMOTION_TONE_TO_MINIMAX = {
    # happy
    "激情": "happy", "激动": "happy", "兴奋": "happy", "开心": "happy",
    "快乐": "happy", "喜悦": "happy", "欢快": "happy", "热情": "happy",
    "活力": "happy", "向往": "happy", "期待": "happy", "积极": "happy",
    # sad
    "悲伤": "sad", "伤感": "sad", "哀伤": "sad", "忧愁": "sad", "失落": "sad",
    "难过": "sad", "遗憾": "sad",
    # angry
    "愤怒": "angry", "气愤": "angry", "生气": "angry", "愤慨": "angry", "不满": "angry",
    # fearful
    "恐惧": "fearful", "害怕": "fearful", "紧张": "fearful", "担忧": "fearful",
    "焦虑": "fearful", "紧迫": "fearful", "急迫": "fearful", "不安": "fearful",
    # surprised
    "惊讶": "surprised", "惊奇": "surprised", "震惊": "surprised", "意外": "surprised",
    "惊喜": "surprised", "好奇": "surprised", "悬念": "surprised",
    # disgusted
    "厌恶": "disgusted", "反感": "disgusted",
    # neutral
    "平静": "neutral", "沉稳": "neutral", "中性": "neutral", "客观": "neutral",
    "温柔": "neutral", "温暖": "neutral", "亲切": "neutral", "自然": "neutral",
    "沉浸": "neutral", "专注": "neutral", "信任": "neutral", "真实": "neutral",
    "共鸣": "neutral", "引导": "neutral", "叙事": "neutral", "专业": "neutral",
    # 英文取值直通
    "happy": "happy", "sad": "sad", "angry": "angry", "fearful": "fearful",
    "disgusted": "disgusted", "surprised": "surprised", "neutral": "neutral",
}


def _map_emotion(tone: str) -> str:
    """文案 emotion_tone -> minimax emotion 取值，未命中返回空（用 minimax 默认）。

    支持复合描述（如"焦虑、共鸣"）：按分隔符拆分，取第一个匹配的词。
    """
    if not tone:
        return ""
    import re
    t = tone.strip()
    # 整体直通
    if t.lower() in EMOTION_TONE_TO_MINIMAX:
        return EMOTION_TONE_TO_MINIMAX[t.lower()]
    # 复合描述：按分隔符拆分，取第一个匹配
    for part in re.split(r"[、,，/；;\s]+", t):
        p = part.strip().lower()
        if p in EMOTION_TONE_TO_MINIMAX:
            return EMOTION_TONE_TO_MINIMAX[p]
    return ""


class TTSAgent(BaseStageAgent):
    def get_task_type(self) -> TaskType:
        return TaskType.GENERAL

    async def execute(self, state: ProjectState, stage: StageState) -> dict[str, Any]:
        """逐段 TTS：每段文案单独合成，精确时长，拼接成完整音频"""
        cw_output = state.get_stage_output("copywriting")
        voice_output = state.get_stage_output("voice_selection")

        if not cw_output:
            return {"data": {"audio_path": "", "word_timestamps": [], "paragraph_timing": []},
                    "confidence": 20.0}

        paragraphs = cw_output.get("paragraphs", [])

        # 获取选中的音色
        voice_key = "zh-CN-YunxiNeural"
        if voice_output:
            selected = voice_output.get("selected", "")
            if selected:
                from ..config import get_domain_config
                try:
                    domain = get_domain_config(state.domain)
                    voices = domain.get_voices()
                    if selected in voices:
                        v = voices[selected]
                        # 优先 minimax_voice_id（克隆音色直传），否则 edge_tts_voice 映射
                        voice_key = v.get("minimax_voice_id") or v.get("edge_tts_voice", voice_key)
                except Exception:
                    pass

        audio_dir = f"data/projects/{state.project_id}/audio"
        seg_paths: list[str] = []
        paragraph_timing: list[dict] = []
        word_timestamps: list[dict] = []
        t = 0.0

        # 逐段 TTS
        for i, p in enumerate(paragraphs):
            text = p.get("text", "")
            if not text:
                continue
            emotion = _map_emotion(p.get("emotion_tone", ""))
            seg_path = f"{audio_dir}/voice_{i}.mp3"
            # TTS 输入：内部句号 。换成逗号 ，（短停顿 0.27s vs 句号 0.79s），保留末尾 。作段落结束
            # 字幕文本不变（仍显示原 。），仅影响配音语流
            tts_text = text.replace("。", "，")
            if text.endswith("。"):
                tts_text = tts_text[:-1] + "。"
            try:
                # speed: 从 settings 读（OPENCUT_TTS_SPEED），默认 1.0
                from ..config import get_settings
                tts_speed = get_settings().tts_speed
                await generate_tts(tts_text, voice_key, seg_path, emotion=emotion, speed=tts_speed)
            except Exception as e:
                log.error(f"TTS 段 {i} 失败: {e}")
                return {"data": {"audio_path": "", "error": str(e),
                                 "paragraph_timing": [], "word_timestamps": []},
                        "confidence": 20.0}
            dur = _probe_duration(seg_path)
            seg_paths.append(seg_path)
            paragraph_timing.append({
                "index": i, "start": round(t, 3), "end": round(t + dur, 3),
                "duration": round(dur, 3), "text": text,
            })
            # 词级时间戳：该段字符均匀分布在段时长内（绝对时间，供兼容用）
            chars = list(text.replace(" ", "").replace("\n", ""))
            char_dur = dur / len(chars) if chars else 0
            for j, c in enumerate(chars):
                word_timestamps.append({
                    "word": c,
                    "start": round(t + j * char_dur, 3),
                    "end": round(t + (j + 1) * char_dur, 3),
                })
            t += dur

        if not seg_paths:
            return {"data": {"audio_path": "", "paragraph_timing": [], "word_timestamps": []},
                    "confidence": 20.0}

        # 拼接成完整音频
        full_path = f"{audio_dir}/voice.mp3"
        try:
            _concat_audio(seg_paths, full_path)
        except Exception as e:
            log.error(f"音频拼接失败: {e}")
            return {"data": {"audio_path": "", "error": str(e),
                             "paragraph_timing": paragraph_timing, "word_timestamps": []},
                    "confidence": 20.0}

        full_text = " ".join(p.get("text", "") for p in paragraphs)
        return {
            "data": {
                "audio_path": full_path,
                "word_timestamps": word_timestamps,
                "paragraph_timing": paragraph_timing,
                "full_text": full_text,
                "transcribe_method": "tts-per-paragraph",
            },
            "confidence": 80.0,
        }

    def _build_prompt(self, *a): return ""
    def _parse_output(self, r): return {}
