"""BGM匹配 Agent - 从领域曲库匹配BGM"""
from __future__ import annotations
from ..providers.selector import TaskType
from .base_agent import BaseStageAgent

class BGMAgent(BaseStageAgent):
    def get_task_type(self): return TaskType.BGM_SELECTION

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
