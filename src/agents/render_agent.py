"""渲染 Agent - 调用Remotion渲染+FFmpeg编码"""
from __future__ import annotations
import logging
from typing import Any
from ..orchestrator.state import ProjectState, StageState
from ..providers.selector import TaskType
from ..tools.remotion_renderer import RemotionRenderer
from ..quality.post_render_validator import validate_video, format_report
from .base_agent import BaseStageAgent

log = logging.getLogger(__name__)


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

        segments = storyboard.get("segments", []) if storyboard else []
        voice_path = tts_output.get("audio_path", "") if tts_output else ""
        bgm_path = bgm_output.get("bgm_path", "") if bgm_output else ""
        bgm_volume = bgm_output.get("volume", 0.25) if bgm_output else 0.25

        # 断链1修复：将 tts word_timestamps 按时间段合并到 segments
        word_timestamps = tts_output.get("word_timestamps", []) if tts_output else []
        if word_timestamps and segments:
            segments = self._merge_word_timestamps(segments, word_timestamps)

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
                src = _Path.cwd() / src
            if not src.exists():
                return asset_path
            dest = public_dir / src.name
            if not dest.exists():
                shutil.copy2(src, dest)
            return f"{state.project_id}/{src.name}"

        # 校验 segment/cover images 是真实文件；storyboard AI 可能编造文件名，不存在则用素材兜底
        material_files = [m.get("file", "") for m in state.materials if m.get("file")]
        for i, seg in enumerate(segments):
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
        )

        output_path = f"data/projects/{state.project_id}/output/final.mp4"
        renderer = RemotionRenderer(
            remotion_dir=get_settings().remotion_dir,
            fps=get_settings().remotion_fps,
        )

        try:
            renderer.render(render_data, output_path)
        except Exception as e:
            log.error(f"Remotion渲染失败: {e}")
            return {"data": {"video_path": "", "error": str(e)}, "confidence": 20.0}

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
        """将全局 word_timestamps 按时间段分配到各 segment"""
        merged = []
        for seg in segments:
            seg_start = seg.get("time_start", 0.0)
            seg_end = seg_start + seg.get("actual_duration", 3.0)
            # 找出属于这个 segment 的词
            seg_words = [
                {"word": w["word"], "start": w["start"] - seg_start, "end": w["end"] - seg_start}
                for w in word_timestamps
                if w.get("start", 0) >= seg_start and w.get("start", 0) < seg_end
            ]
            merged_seg = dict(seg)
            merged_seg["subtitle_words"] = seg_words
            merged.append(merged_seg)
        return merged

    def _build_prompt(self, *a): return ""
    def _parse_output(self, r): return {}
