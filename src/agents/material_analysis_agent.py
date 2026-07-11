"""素材分析 Agent - 分析上传图片的场景、情绪、质量"""
from __future__ import annotations
from typing import Any
from ..providers.selector import TaskType
from .base_agent import BaseStageAgent


class MaterialAnalysisAgent(BaseStageAgent):
    def get_task_type(self) -> TaskType:
        return TaskType.IMAGE_ANALYSIS

    def _build_prompt(self, skill_context, upstream_context, user_note, input_data):
        materials = input_data.get("materials", [])
        return f"""{skill_context}

【素材文件列表】
{materials}

{f'【用户备注】{user_note}' if user_note else ''}

分析每张图片的场景、情绪、质量评分。输出JSON：
{{"images": [{{"file": "", "scene": "", "emotion": "", "score": 3}}], "destination": "", "scene_types": []}}"""

    def _parse_output(self, response):
        return self._extract_json(response)

    async def execute(self, state: ProjectState, stage: StageState) -> dict[str, Any]:
        """重写execute：先做基础图片检查，再调AI"""
        import os
        materials = stage.input_data.get("materials", [])
        basic_analyses = []
        for m in materials:
            fpath = m.get("file", "")
            if fpath and os.path.exists(fpath):
                size = os.path.getsize(fpath)
                score = min(5, max(1, size // 100000))
                basic_analyses.append({"file": fpath, "size": size, "basic_score": score})
        stage.input_data["basic_analyses"] = basic_analyses
        return await super().execute(state, stage)

