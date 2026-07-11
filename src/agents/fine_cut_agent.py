"""精剪编排 Agent - 细粒度调整时序和转场"""
from __future__ import annotations
from ..providers.selector import TaskType
from .base_agent import BaseStageAgent

class FineCutAgent(BaseStageAgent):
    def get_task_type(self): return TaskType.FINE_CUT

    def _build_prompt(self, skill_context, upstream_context, user_note, input_data):
        return f"""{skill_context}

【上游数据】
{upstream_context}

精剪参数调整。输出JSON：
{{"adjustments": [{{"index": 0, "duration_delta": 0.0, "transition_duration": 0.4}}]}}"""

    def _parse_output(self, response):
        data = self._extract_json(response)
        # AI 偶发返回空，给默认空调整列表避免 "输出为空" 阻断
        if not data:
            data = {"adjustments": []}
        elif "adjustments" not in data:
            data["adjustments"] = []
        return data
