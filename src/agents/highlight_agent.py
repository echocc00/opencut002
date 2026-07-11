"""亮点选择 Agent - 两阶段拆分第一步：生成2-3套亮点选择方案"""
from __future__ import annotations
import json
from ..providers.selector import TaskType
from .base_agent import BaseStageAgent

class HighlightAgent(BaseStageAgent):
    def get_task_type(self): return TaskType.GENERAL

    def _build_prompt(self, skill_context, upstream_context, user_note, input_data):
        highlights = input_data.get("highlights", [])
        hl_text = json.dumps(highlights, ensure_ascii=False, indent=2)
        return f"""{skill_context}

【可用亮点库】
{hl_text}

【上游数据】
{upstream_context}

生成2-3套不同的亮点选择方案。每套方案选1-3个亮点。输出JSON：
{{"options": [{{"highlight_ids": [], "highlight_names": [], "selection_reason": "", "presentation_style": "", "expected_effect": ""}}], "selected": -1}}"""

    def _parse_output(self, response):
        return self._extract_json(response)
