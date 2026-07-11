"""分镜脚本 Agent - 生成分镜（段落->图片+时长+转场）"""
from __future__ import annotations
from ..providers.selector import TaskType
from .base_agent import BaseStageAgent

class StoryboardAgent(BaseStageAgent):
    def get_task_type(self): return TaskType.STORYBOARD

    def _build_prompt(self, skill_context, upstream_context, user_note, input_data):
        # 注入TTS总时长，要求分镜时长必须匹配
        tts_duration = input_data.get("tts_total_duration", 0)
        tts_hint = ""
        if tts_duration > 0:
            tts_hint = f"""
【重要约束 - 分镜时长必须匹配TTS音频时长】
TTS配音总时长: {tts_duration:.1f}秒
所有分镜段落的 actual_duration 之和必须等于 {tts_duration:.1f}秒（允许±1秒误差）。
请根据文案段落数量和TTS时长合理分配每段时长。
"""
        return f"""{skill_context}

{tts_hint}

【上游数据】
{upstream_context}

生成分镜。每段包含图片、时长、字幕、转场。输出JSON：
{{"segments": [{{"index": 0, "image": "", "actual_duration": 3.5, "time_start": 0.0, "subtitle": "", "transition": "crossfade", "subtitle_words": []}}], "total_duration": {tts_duration:.1f}}}"""

    def _parse_output(self, response):
        return self._extract_json(response)
