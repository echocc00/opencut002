"""选题策划 Agent - 生成2-3个选题方向"""
from __future__ import annotations
from ..providers.selector import TaskType
from .base_agent import BaseStageAgent

class TopicAgent(BaseStageAgent):
    def get_task_type(self): return TaskType.TOPIC_GENERATION

    def _build_prompt(self, skill_context, upstream_context, user_note, input_data):
        return f"""{skill_context}

【上游数据】
{upstream_context}

{f'【用户备注】{user_note}' if user_note else ''}

生成2-3个选题方向。输出JSON：
{{"directions": [{{"name": "", "hook": "", "psychology": "", "ref_type": "", "why_work": ""}}], "selected": -1}}"""

    def _parse_output(self, response):
        return self._extract_json(response)
