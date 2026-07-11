"""参考视频分析 Agent - 分析爆款视频，生成改编方案"""
from __future__ import annotations
import json
from typing import Any
from ..orchestrator.state import ProjectState, StageState
from ..providers.selector import TaskType
from ..tools.video_downloader import download_video
from ..tools.scene_detector import detect_scenes, extract_keyframes
from ..tools.transcriber import Transcriber
from .base_agent import BaseStageAgent


class ReferenceAnalyzerAgent(BaseStageAgent):
    def get_task_type(self): return TaskType.GENERAL

    async def execute(self, state: ProjectState, stage: StageState) -> dict[str, Any]:
        url = stage.input_data.get("reference_url", "")
        if not url:
            return {"data": {"error": "no reference_url"}, "confidence": 10.0}

        # 1. 下载视频
        video_path = download_video(url)
        if not video_path:
            return {"data": {"error": "download failed"}, "confidence": 10.0}

        # 2. 场景检测
        scene_info = detect_scenes(video_path)

        # 3. 提取关键帧
        keyframes = extract_keyframes(video_path, f"data/projects/{state.project_id}/keyframes")

        # 4. 转录
        transcriber = Transcriber(device="cpu")
        try:
            transcript = transcriber.transcribe(video_path)
            transcript_text = transcript.full_text
        except Exception:
            transcript_text = ""

        # 5. AI综合分析
        stage.input_data.update({
            "scene_info": scene_info, "transcript": transcript_text[:1000], "keyframes": keyframes,
        })
        return await super().execute(state, stage)

    def _build_prompt(self, skill_context, upstream_context, user_note, input_data):
        scene = input_data.get("scene_info", {})
        return f"""{skill_context}

【参考视频分析】
时长: {scene.get('duration', 0):.1f}s
场景数: {scene.get('scene_count', 0)}
节奏: {scene.get('pacing', 'unknown')}
转录: {input_data.get('transcript', '')[:500]}

生成2-3套改编方案。输出JSON：
{{"plans": [{{"concept_name": "", "what_to_keep": [], "what_to_change": [], "visual_treatment": "", "angle": "", "sample_opening": ""}}]}}"""

    def _parse_output(self, response):
        return self._extract_json(response)
