"""BGM匹配 Agent - 从领域曲库匹配BGM"""
from __future__ import annotations
import logging
from typing import Any
from ..orchestrator.state import ProjectState, StageState
from ..providers.selector import TaskType
from .base_agent import BaseStageAgent

log = logging.getLogger(__name__)


class BGMAgent(BaseStageAgent):
    def get_task_type(self): return TaskType.BGM_SELECTION

    async def execute(self, state: ProjectState, stage: StageState) -> dict[str, Any]:
        """BGM 曲库为空时显式返回空路径，不调 AI（避免从空列表选出不存在的 BGM）"""
        available = stage.input_data.get("available_bgm", [])
        if not available:
            log.warning(f"BGM 曲库为空（domain={state.domain}），跳过 BGM 轨道")
            return {"data": {"bgm_path": "", "bgm_category": "", "volume": 0.25,
                             "candidates": [], "selected_path": ""},
                    "confidence": 60.0}
        return await super().execute(state, stage)

    def _build_prompt(self, skill_context, upstream_context, user_note, input_data):
        bgm_list = input_data.get("available_bgm", [])
        return f"""{skill_context}

【可用BGM】
{bgm_list}

【上游数据】
{upstream_context}

推荐2-3首BGM。输出JSON：
{{"candidates": [{{"path": "", "category": "", "reason": ""}}], "selected_path": "", "volume": 0.25}}"""

    def _parse_output(self, response):
        return self._extract_json(response)
