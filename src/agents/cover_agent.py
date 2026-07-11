"""封面设计 Agent - 从关键帧选封面"""
from __future__ import annotations
from ..providers.selector import TaskType
from .base_agent import BaseStageAgent

class CoverAgent(BaseStageAgent):
    def get_task_type(self): return TaskType.COVER

    def _build_prompt(self, skill_context, upstream_context, user_note, input_data):
        return f"""{skill_context}

【上游数据】
{upstream_context}

选取2-3个封面候选。输出JSON：
{{"cover_candidates": ["frame_0.jpg", "frame_3.jpg"], "selected": -1}}"""

    def _parse_output(self, response):
        return self._extract_json(response)
