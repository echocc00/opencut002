"""标题优化 Agent - 生成3-5个标题候选"""
from __future__ import annotations
from ..providers.selector import TaskType
from .base_agent import BaseStageAgent

class TitleAgent(BaseStageAgent):
    def get_task_type(self): return TaskType.PUBLISHING

    def _build_prompt(self, skill_context, upstream_context, user_note, input_data):
        return f"""{skill_context}

【上游数据】
{upstream_context}

生成3-5个标题。输出JSON：
{{"titles": ["标题1", "标题2"], "selected": -1}}"""

    def _parse_output(self, response):
        return self._extract_json(response)
