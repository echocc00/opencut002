"""渲染 Agent - 调用Remotion渲染+FFmpeg编码"""
from __future__ import annotations
import json
import logging
import os
from typing import Any
from ..orchestrator.state import ProjectState, StageState
from ..providers.selector import TaskType
from ..tools.remotion_renderer import RemotionRenderer
from ..utils.subtitle_split import split_subtitle_adaptive, compute_screen_durations, _clean_chars_count
from ..quality.post_render_validator import validate_video, format_report
from .base_agent import BaseStageAgent

log = logging.getLogger(__name__)


def _ai_label_enabled() -> bool:
    """读 OPENCUT_AI_LABEL 环境变量决定是否渲染 AI 生成标识（默认关）。
    合规储备：B2C 公网上线时设 OPENCUT_AI_LABEL=1 即可开启，无需改代码。"""
    return os.environ.get("OPENCUT_AI_LABEL", "").strip().lower() in ("1", "true", "yes", "on")


def _subtitle_split_enabled() -> bool:
    """屏级字幕切分（v0.6.1）。默认开（forced_align 对齐段自动屏级）。
    OPENCUT_SUBTITLE_SPLIT=0 关闭，回退 v0.6.0 行级 subtitle_lines。"""
    return os.environ.get("OPENCUT_SUBTITLE_SPLIT", "1").strip().lower() in ("1", "true", "yes", "on")


class RenderAgent(BaseStageAgent):
    def get_task_type(self) -> TaskType:
        return TaskType.GENERAL

    async def execute(self, state: ProjectState, stage: StageState) -> dict[str, Any]:
        """渲染不调AI，直接调Remotion"""
        storyboard = state.get_stage_output("storyboard")
        tts_output = state.get_stage_output("tts")
        bgm_output = state.get_stage_output("bgm")
        title_output = state.get_stage_output("title")
        cover_output = state.get_stage_output("cover")

        title = ""
        if title_output and title_output.get("titles"):
            sel = title_output.get("selected", 0)
            if 0 <= sel < len(title_output["titles"]):
                title = title_output["titles"][sel]

        cover_image = ""
        if cover_output:
            candidates = cover_output.get("cover_candidates", [])
            cov_sel = cover_output.get("selected", -1)
            if 0 <= cov_sel < len(candidates):
                cover_image = candidates[cov_sel]

        voice_path = tts_output.get("audio_path", "") if tts_output else ""
        bgm_path = bgm_output.get("bgm_path", "") if bgm_output else ""
        bgm_volume = bgm_output.get("volume", 0.25) if bgm_output else 0.25
        word_timestamps = tts_output.get("word_timestamps", []) if tts_output else ""

        # 按文案段落构建分镜：一段一句一画面，时长=该段在音频中的真实时间
        # 不用 storyboard AI 猜的分段（边界和句子不对齐 -> 句子被切到两个画面、最后一句丢失）
        cw_output = state.get_stage_output("copywriting")
        im_output = state.get_stage_output("image_matching")
        matches = im_output.get("matches", {}) if im_output else {}
        text_cards = im_output.get("text_cards", []) if im_output else []
        sb_segments = storyboard.get("segments", []) if storyboard else []
        paragraph_timing = tts_output.get("paragraph_timing", []) if tts_output else []
        segments = self._build_paragraph_segments(paragraph_timing, matches, sb_segments, text_cards)

        # A1/A2: forced align 成功的段做字幕同步
        # v0.6.1: OPENCUT_SUBTITLE_SPLIT（默认开）-> 屏级切分（N 屏/段，真实时间戳驱动）
        #         split 关 -> v0.6.0 行级 subtitle_lines
        aligned_segments = set(tts_output.get("aligned_segments", [])) if tts_output else set()
        if aligned_segments and word_timestamps:
            sb_image_map = {s.get("index", i): s.get("image", "")
                            for i, s in enumerate(sb_segments)}
            material_files_all = [m.get("file", "") for m in state.materials if m.get("file")]
            text_cards_set = set(text_cards or [])
            split_enabled = _subtitle_split_enabled()

            new_segments: list[dict] = []
            for seg in segments:
                i = seg.get("index")
                if i in aligned_segments and split_enabled:
                    pt = next((p for p in paragraph_timing if p["index"] == i), None)
                    if pt is not None:
                        screen_segs = self._build_screen_segments(
                            pt, matches.get(str(i), ""), sb_image_map.get(i, ""),
                            material_files_all, text_cards_set, word_timestamps,
                            seg.get("transition", "crossfade"))
                        if screen_segs:
                            new_segments.extend(screen_segs)
                            continue
                    # 屏级切分失败（单屏/无时间戳）-> 走段级整段
                    new_segments.append(seg)
                elif i in aligned_segments and not split_enabled:
                    # v0.6.0 行级 subtitle_lines
                    seg_wts = self._merge_word_timestamps([seg], word_timestamps)[0].get("subtitle_words", [])
                    if seg_wts:
                        seg["subtitle_lines"] = self._chunk_subtitle_lines(seg_wts, seg.get("subtitle", ""))
                    new_segments.append(seg)
                else:
                    # 非对齐段：整段淡入（spring）
                    new_segments.append(seg)
            segments = new_segments

        # 从领域配置读取style并注入
        from ..config import get_domain_config, get_settings
        try:
            domain_cfg = get_domain_config(state.domain)
            style = domain_cfg.get_style()
            visual_style = style.get("visual", {})
            active_color = visual_style.get("active_color", "#D4734A")
        except Exception:
            active_color = "#D4734A"

        # 把素材（图片/音频）复制到 remotion/public/{project_id}/ 并改写为 public 相对路径
        # Remotion headless 浏览器禁止 file:// 资源，只能走 staticFile（public/ 下）
        import shutil
        from pathlib import Path as _Path
        public_dir = _Path(get_settings().remotion_dir) / "public" / state.project_id
        public_dir.mkdir(parents=True, exist_ok=True)

        def _stage_asset(asset_path: str) -> str:
            if not asset_path:
                return ""
            src = _Path(asset_path)
            if not src.is_absolute():
                src = _Path.cwd() / asset_path
            if not src.exists():
                return asset_path
            # 人脸遮盖（opt-in，OPENCUT_FACE_MASK=1）：图片用 masked 副本，非图片返回原图
            from ..tools.face_masker import get_masked_path
            from ..tools.auto_reframe import get_reframed_path
            staged = _Path(get_masked_path(str(src)))
            staged = _Path(get_reframed_path(str(staged)))  # v0.6.2 链式：masked -> reframed
            dest = public_dir / staged.name
            # 检测 stale: 不存在、源比 dest 新、或大小不同都视为过期，重拷
            stale = True
            if dest.exists():
                try:
                    src_stat = staged.stat()
                    dest_stat = dest.stat()
                    if dest_stat.st_mtime >= src_stat.st_mtime and dest_stat.st_size == src_stat.st_size:
                        stale = False
                except OSError:
                    pass
            if stale:
                shutil.copy2(staged, dest)
            return f"{state.project_id}/{staged.name}"

        # 校验 segment/cover images 是真实文件；storyboard AI 可能编造文件名，不存在则用素材兜底
        material_files = [m.get("file", "") for m in state.materials if m.get("file")]
        for i, seg in enumerate(segments):
            if seg.get("text_card"):
                continue  # 文字卡段不配图，不兜底复用
            img = seg.get("image", "")
            if not img or not _Path(img).exists():
                seg["image"] = material_files[i % len(material_files)] if material_files else ""
        if cover_image and not _Path(cover_image).exists():
            cover_image = material_files[0] if material_files else ""

        for seg in segments:
            if seg.get("image"):
                seg["image"] = _stage_asset(seg["image"])
        cover_image = _stage_asset(cover_image)
        voice_path = _stage_asset(voice_path)
        bgm_path = _stage_asset(bgm_path)

        render_data = RemotionRenderer.build_render_data(
            title=title, title_duration=2.0,
            segments=segments, voice_path=voice_path,
            bgm_path=bgm_path, bgm_volume=bgm_volume,
            style={"activeColor": active_color},
            cover_image=cover_image, domain=state.domain,
            ai_label=_ai_label_enabled(),
        )

        output_path = f"data/projects/{state.project_id}/output/final.mp4"
        renderer = RemotionRenderer(
            remotion_dir=get_settings().remotion_dir,
            fps=get_settings().remotion_fps,
        )

        # 渲染缓存（OPENCUT_CACHE=1）：相同 render_data 跳过 Remotion 渲染，直接拷缓存 mp4
        import hashlib
        from ..tools.result_cache import is_enabled as _cache_enabled, _cache_dir as _cache_dir
        _render_key = hashlib.sha256(
            json.dumps(render_data, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:16]
        _cache_mp4 = _cache_dir("render") / f"{_render_key}.mp4"
        _cache_hit = False
        if _cache_enabled() and _cache_mp4.exists():
            try:
                import shutil as _shutil
                _Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                _shutil.copy2(_cache_mp4, output_path)
                _cache_hit = True
                log.info(f"渲染缓存命中，跳过 Remotion: {_render_key}")
            except OSError:
                _cache_hit = False

        if not _cache_hit:
            try:
                renderer.render(render_data, output_path)
            except Exception as e:
                log.error(f"Remotion渲染失败: {e}")
                return {"data": {"video_path": "", "error": str(e)}, "confidence": 20.0}
            # 写缓存
            if _cache_enabled() and _Path(output_path).exists():
                try:
                    import shutil as _shutil
                    _shutil.copy2(output_path, _cache_mp4)
                except OSError:
                    pass

        expected_duration = sum(s.get("actual_duration", 3.0) for s in segments) + 2.0
        result = validate_video(output_path, expected_duration=expected_duration)
        report = format_report(result)

        self.decision_logger.log(
            stage="render", provider="remotion", provider_score=100,
            reasoning=f"渲染 {output_path}，{'通过' if result.passed else '未通过'}质量自检",
            confidence=90.0 if result.passed else 40.0,
            output_summary=f"时长:{result.duration:.1f}s 分辨率:{result.resolution}",
        )

        return {
            "data": {"video_path": output_path, "duration": result.duration,
                     "quality_report": {"passed": result.passed, "report": report}},
            "confidence": 90.0 if result.passed else 40.0,
        }

    def _merge_word_timestamps(self, segments: list[dict], word_timestamps: list[dict]) -> list[dict]:
        """将全局 word_timestamps 按时间段分配到各 segment（全局->段内相对时间）"""
        merged = []
        for seg in segments:
            seg_start = seg.get("time_start", 0.0)
            seg_end = seg_start + seg.get("actual_duration", 3.0)
            seg_words = [
                {"word": w["word"], "start": w["start"] - seg_start, "end": w["end"] - seg_start}
                for w in word_timestamps
                if w.get("start", 0) >= seg_start and w.get("start", 0) < seg_end
            ]
            merged_seg = dict(seg)
            merged_seg["subtitle_words"] = seg_words
            merged.append(merged_seg)
        return merged

    @staticmethod
    def _chunk_subtitle_lines(seg_words: list[dict], full_text: str,
                              max_chars: int = 16) -> list[dict]:
        """把段内逐字时间戳 + 原文打包成 <=max_chars 的字幕行。

        seg_words: [{word,start,end}]（段内相对秒，仅汉字，forced align 输出）
        full_text: 原文（含标点）。先按标点切短语+超长硬切 max_chars，再为每行
        找首尾汉字在 seg_words 的时间戳 -> {text,start,end}。汉字数不匹配回退均分。
        """
        if not seg_words or not full_text:
            return []

        PHRASE_BREAK = set("。！？!?\n，、；;：…")
        # 1. 原文按标点切短语，每短语独立成行（标点必断），超 max_chars 硬切
        phrases: list[str] = []
        cur = ""
        for ch in full_text:
            cur += ch
            if ch in PHRASE_BREAK:
                phrases.append(cur)
                cur = ""
        if cur:
            phrases.append(cur)

        lines_text: list[str] = []
        for p in phrases:
            p = p.strip()
            if not p:
                continue
            if len(p) <= max_chars:
                lines_text.append(p)
            else:
                # 超长无标点短语硬切
                for i in range(0, len(p), max_chars):
                    lines_text.append(p[i:i + max_chars].strip())

        # 2. 汉字在原文中的位置 -> 对应 seg_words 索引（顺序一致）
        hanzi_pos = [i for i, c in enumerate(full_text) if "一" <= c <= "鿿"]
        if len(hanzi_pos) != len(seg_words):
            log.warning(f"汉字数不匹配（text={len(hanzi_pos)} align={len(seg_words)}），回退均分")
            seg_start = seg_words[0]["start"] if seg_words else 0
            seg_end = seg_words[-1]["end"] if seg_words else 0
            if not lines_text:
                return []
            per = (seg_end - seg_start) / len(lines_text)
            return [{"text": t, "start": round(seg_start + i * per, 3),
                     "end": round(seg_start + (i + 1) * per, 3)} for i, t in enumerate(lines_text)]

        # 3. 每行找首尾汉字 -> 时间戳
        result = []
        search_pos = 0
        for line_text in lines_text:
            start_pos = full_text.find(line_text, search_pos)
            if start_pos < 0:
                continue
            end_pos = start_pos + len(line_text)
            search_pos = end_pos
            first_wi = None
            last_wi = None
            for j, tp in enumerate(hanzi_pos):
                if start_pos <= tp < end_pos:
                    if first_wi is None:
                        first_wi = j
                    last_wi = j
            if first_wi is not None and last_wi is not None:
                result.append({
                    "text": line_text,
                    "start": round(seg_words[first_wi]["start"], 3),
                    "end": round(seg_words[last_wi]["end"], 3),
                })
        return result

    def _build_screen_segments(
        self, pt: dict, match_img: str, sb_img: str, material_files: list[str],
        text_cards: set[int], word_timestamps: list[dict], transition: str,
    ) -> list[dict] | None:
        """对单个 forced_align 对齐段做屏级切分，返回 N 个屏 segment（或 None 走段级）。

        时间戳按时间段从全局 word_timestamps 过滤（兼容 hanzi-only 对齐输出 +
        非对齐段造假输出的混合数组），转段内相对后喂给 compute_screen_durations。
        4 层图候选：匹配图 -> storyboard 图 -> 素材轮换，屏间轮换 + Ken Burns。
        """
        text = pt.get("text", "")
        seg_start = pt["start"]
        seg_end = seg_start + pt["duration"]
        if not text or pt["duration"] <= 0:
            return None

        seg_wts_global = [w for w in word_timestamps
                          if seg_start <= w.get("start", 0) < seg_end]
        seg_wts_local = [
            {"word": w["word"],
             "start": round(w["start"] - seg_start, 3),
             "end": round(w["end"] - seg_start, 3)}
            for w in seg_wts_global
        ]

        screens = split_subtitle_adaptive(text, audio_duration=pt["duration"])
        if len(screens) <= 1:
            return None  # 单屏无意义，走段级

        screen_timings = compute_screen_durations(
            text, seg_start, pt["duration"], seg_wts_local, screens)
        if not screen_timings:
            return None

        # 4 层图候选（去重，最多 8 张供屏间轮换）
        cands: list[str] = []
        if match_img:
            cands.append(match_img)
        if sb_img and sb_img not in cands:
            cands.append(sb_img)
        for m in material_files:
            if m and m not in cands:
                cands.append(m)
                if len(cands) >= 8:
                    break
        is_text_card = (pt["index"] in text_cards) and not cands

        result: list[dict] = []
        for scr_idx, (screen_text, timing) in enumerate(zip(screens, screen_timings)):
            image = cands[scr_idx % len(cands)] if cands else ""
            result.append({
                "index": pt["index"],
                "screen_index": scr_idx,
                "screens_total": len(screens),
                "image": image,
                "actual_duration": round(timing["duration"], 3),
                "time_start": round(timing["start"], 3),
                "subtitle": screen_text,
                "transition": transition if scr_idx == 0 else "fade",
                "text_card": is_text_card,
                "audio_start": round(seg_start, 3),
                "audio_duration": round(pt["duration"], 3),
                "screen_chars": _clean_chars_count(screen_text),
            })
        return result

    def _build_paragraph_segments(self, paragraph_timing: list[dict],
                                  matches: dict, sb_segments: list[dict],
                                  text_cards: list[int] | None = None) -> list[dict]:
        """按 TTS 段落时间戳构建分镜：一段一画面，时长=该段 TTS 精确时长。

        段落时长来自每段单独 TTS 的 ffprobe 测量（精确），不依赖转录反推。
        字幕整段淡入显示（不再逐词高亮），故不生成 subtitle_words。
        text_cards 中的段标记为文字卡（无图，render 用 TextCardScene）。
        """
        text_cards = text_cards or []
        segments = []
        for pt in paragraph_timing:
            i = pt["index"]
            transition = "crossfade"
            if i < len(sb_segments) and sb_segments[i].get("transition"):
                transition = sb_segments[i]["transition"]
            segments.append({
                "index": i,
                "image": matches.get(str(i), ""),
                "actual_duration": round(pt["duration"], 3),
                "time_start": round(pt["start"], 3),
                "subtitle": pt["text"],
                "transition": transition,
                "text_card": i in text_cards,
            })
        return segments

    def _build_prompt(self, *a): return ""
    def _parse_output(self, r): return {}
