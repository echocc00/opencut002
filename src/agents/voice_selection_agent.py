"""音色选择 Agent - 根据文案情绪推荐音色"""
from __future__ import annotations
from ..providers.selector import TaskType
from .base_agent import BaseStageAgent

class VoiceAgent(BaseStageAgent):
    def get_task_type(self): return TaskType.GENERAL

    def _build_prompt(self, skill_context, upstream_context, user_note, input_data):
        voices = input_data.get("available_voices", {})
        return f"""{skill_context}

【可用音色】
{voices}

【上游数据】
{upstream_context}

推荐2-3个音色。输出JSON：
{{"candidates": [{{"voice_key": "", "reason": ""}}], "selected": ""}}"""

    def _parse_output(self, response):
        return self._extract_json(response)
