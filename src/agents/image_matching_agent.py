"""画面匹配 Agent - 调用 image_matcher 工具匹配文案段落与图片"""
from __future__ import annotations
import logging
from typing import Any
from ..orchestrator.state import ProjectState, StageState
from ..providers.selector import TaskType
from ..tools.image_matcher import match_images
from .base_agent import BaseStageAgent

log = logging.getLogger(__name__)


class ImageMatchingAgent(BaseStageAgent):
    def get_task_type(self) -> TaskType:
        return TaskType.GENERAL

    async def execute(self, state: ProjectState, stage: StageState) -> dict[str, Any]:
        """重写execute：先调工具匹配，AI兜底"""
        cw_output = state.get_stage_output("copywriting")
        ma_output = state.get_stage_output("material_analysis")
        if not cw_output or not ma_output:
            return {"data": {"matches": {}}, "confidence": 30.0}

        paragraphs = cw_output.get("paragraphs", [])
        images = ma_output.get("images", [])

        # 尝试AI匹配
        try:
            ai_complete = None
            try:
                from ..providers.provider_registry import get_provider
                from ..providers.selector import ProviderSelector, TaskType
                selector = ProviderSelector()
                sel = selector.select(TaskType.GENERAL, ["deepseek", "doubao", "qwen"])
                ai_complete = get_provider(sel.winner).complete
            except Exception:
                pass

            matches = await match_images(paragraphs, images, ai_complete)
        except Exception as e:
            log.warning(f"AI匹配失败，用回退: {e}")
            matches = await match_images(paragraphs, images, None)

        return {"data": {"matches": matches}, "confidence": 75.0}

    def _build_prompt(self, *a): return ""
    def _parse_output(self, r): return {}
