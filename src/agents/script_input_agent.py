"""文案驱动模式 Agent - 把用户提供的文案结构化为 copywriting 输出（不调 AI）

用户给文案 + 素材池 -> material_analysis 分析池 -> 本 agent 把文案切成段落塞进
copywriting 输出 -> image_matching 把段落匹配到池图 -> 后续不变。
跳过 web_research/topic/highlight（文案已由用户提供，无需 AI 生成选题/亮点/文案）。
"""
from __future__ import annotations

import re
from typing import Any

from ..orchestrator.state import ProjectState, StageState
from ..providers.selector import TaskType
from .base_agent import BaseStageAgent

# 段落目标长度（汉字字符）：太短 TTS 碎、太长字幕块多。20-40 较自然
_MAX_PARAGRAPH_CHARS = 40
# TTS 语速估算（字符/秒），用于 target_duration 提示（实际以 ffprobe 为准）
_CHARS_PER_SEC = 3.5


class ScriptInputAgent(BaseStageAgent):
    def get_task_type(self) -> TaskType:
        return TaskType.GENERAL

    async def execute(self, state: ProjectState, stage: StageState) -> dict[str, Any]:
        script = (stage.input_data or {}).get("user_script", "")
        if not script:
            return {"data": {"paragraphs": [], "tone": "neutral"}, "confidence": 20.0}
        paragraphs = structure_script(script)
        return {"data": {"paragraphs": paragraphs, "tone": "neutral"}, "confidence": 95.0}

    def _build_prompt(self, *a): return ""
    def _parse_output(self, r): return {}


def structure_script(text: str, max_chars: int = _MAX_PARAGRAPH_CHARS) -> list[dict]:
    """把用户文案切成 ≤max_chars 字的段落（按句末标点/换行断句，贪心打包），
    赋默认字段（target_duration 估算、image_hint 空、emotion_tone neutral）。
    """
    # 按句末标点 + 换行切句子（保留标点）
    parts = re.split(r"(?<=[。！？!?\n])", text)
    sentences = [p.strip() for p in parts if p.strip()]

    paragraphs: list[str] = []
    cur = ""
    for s in sentences:
        # 超长单句先硬切
        while len(s) > max_chars:
            if cur:
                paragraphs.append(cur)
                cur = ""
            paragraphs.append(s[:max_chars])
            s = s[max_chars:]
        if not cur:
            cur = s
        elif len(cur) + len(s) <= max_chars:
            cur += s
        else:
            paragraphs.append(cur)
            cur = s
    if cur:
        paragraphs.append(cur)

    return [
        {
            "text": p,
            "target_duration": round(len(p) / _CHARS_PER_SEC, 1),
            "image_hint": "",
            "highlight_ref": "script",  # script 模式无亮点，占位非空过 postflight 完整性校验
            "emotion_tone": "neutral",
        }
        for p in paragraphs
    ]
