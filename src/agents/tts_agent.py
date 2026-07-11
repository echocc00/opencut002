"""TTS Agent - 生成配音音频 + 词级时间戳"""
from __future__ import annotations
import logging
from typing import Any
from ..orchestrator.state import ProjectState, StageState
from ..providers.selector import TaskType
from ..tools.tts_generator import generate_tts
from ..tools.transcriber import Transcriber
from .base_agent import BaseStageAgent

log = logging.getLogger(__name__)


class TTSAgent(BaseStageAgent):
    def get_task_type(self) -> TaskType:
        return TaskType.GENERAL

    async def execute(self, state: ProjectState, stage: StageState) -> dict[str, Any]:
        """重写execute：调TTS工具 + 转录工具"""
        cw_output = state.get_stage_output("copywriting")
        voice_output = state.get_stage_output("voice_selection")

        if not cw_output:
            return {"data": {"audio_path": "", "word_timestamps": []}, "confidence": 20.0}

        paragraphs = cw_output.get("paragraphs", [])
        full_text = " ".join(p.get("text", "") for p in paragraphs)

        # 获取选中的音色
        voice_key = "zh-CN-YunxiNeural"  # 默认
        if voice_output:
            selected = voice_output.get("selected", "")
            if selected:
                from ..config import get_domain_config
                domain = get_domain_config(state.domain)
                voices = domain.get_voices()
                if selected in voices:
                    voice_key = voices[selected].get("edge_tts_voice", voice_key)

        # 生成TTS
        audio_path = f"data/projects/{state.project_id}/audio/voice.mp3"
        try:
            await generate_tts(full_text, voice_key, audio_path)
        except Exception as e:
            log.error(f"TTS生成失败: {e}")
            return {"data": {"audio_path": "", "word_timestamps": [], "error": str(e)}, "confidence": 20.0}

        # 转录获取词级时间戳；whisperx 可信度高，fallback 是字符估算需降级
        transcriber = Transcriber(device="cpu")
        method = "fallback"
        try:
            result = transcriber.transcribe(audio_path, known_text=full_text)
            word_timestamps = result.words
            method = result.method
        except Exception as e:
            log.warning(f"转录失败: {e}")
            word_timestamps = []

        if not word_timestamps:
            transcribe_conf = 40.0
        elif method == "whisperx":
            transcribe_conf = 80.0
        else:
            transcribe_conf = 50.0

        return {
            "data": {
                "audio_path": audio_path,
                "word_timestamps": word_timestamps,
                "full_text": full_text,
                "transcribe_method": method,
            },
            "confidence": transcribe_conf,
        }

    def _build_prompt(self, *a): return ""
    def _parse_output(self, r): return {}
