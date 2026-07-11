"""节奏编排 Agent - 计算时长分配+BGM踩点"""
from __future__ import annotations
from ..providers.selector import TaskType
from .base_agent import BaseStageAgent

class RhythmAgent(BaseStageAgent):
    def get_task_type(self): return TaskType.RHYTHM

    def _build_prompt(self, skill_context, upstream_context, user_note, input_data):
        return f"""{skill_context}

【上游数据】
{upstream_context}

计算节奏编排。输出JSON：
{{"segment_timings": [{{"index": 0, "duration": 3.5, "transition_point": 0.0}}], "bgm_start_offset": 0.0}}"""

    def _parse_output(self, response):
        return self._extract_json(response)
