"""文案创作 Agent - 两阶段拆分第二步：根据确认的亮点方案写文案"""
from __future__ import annotations
from ..providers.selector import TaskType
from .base_agent import BaseStageAgent

class CopywritingAgent(BaseStageAgent):
    def get_task_type(self): return TaskType.COPYWRITING

    def _build_prompt(self, skill_context, upstream_context, user_note, input_data):
        highlights = input_data.get("confirmed_highlights", {})
        return f"""{skill_context}

【已确认的亮点方案 - 必须体现】
亮点: {', '.join(highlights.get('highlight_names', []))}
呈现方式: {highlights.get('presentation_style', '')}
预期效果: {highlights.get('expected_effect', '')}

每段文案必须标注 highlight_ref（对应亮点ID）。

【上游数据】
{upstream_context}

{f'【用户备注】{user_note}' if user_note else ''}

生成4-8段文案。输出JSON：
{{"paragraphs": [{{"text": "", "target_duration": 3.5, "image_hint": "", "highlight_ref": "", "emotion_tone": ""}}], "tone": ""}}"""

    def _parse_output(self, response):
        return self._extract_json(response)
