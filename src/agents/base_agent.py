"""StageAgent 框架 - 每个阶段的 AI Agent 基类"""
from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

from ..orchestrator.state import ProjectState, StageState
from ..providers.selector import ProviderSelector, TaskType
from .decision_logger import DecisionLogger
from .skill_loader import SkillLoader
from .confidence_scorer import calculate_confidence, get_required_keys

log = logging.getLogger(__name__)


class BaseStageAgent(ABC):
    def __init__(
        self,
        skill_loader: SkillLoader,
        provider_selector: ProviderSelector,
        decision_logger: DecisionLogger,
        preference_profile=None,
        annotation_store=None,
    ):
        self.skill_loader = skill_loader
        self.provider_selector = provider_selector
        self.decision_logger = decision_logger
        self.preference_profile = preference_profile
        self.annotation_store = annotation_store

    async def execute(self, state: ProjectState, stage: StageState) -> dict[str, Any]:
        # 1. 构建上下文
        skill_context = self.skill_loader.build_prompt_context(stage.name)
        upstream_context = self._build_upstream_context(state, stage)
        user_note = state.user_notes.get(stage.name, "")

        # #12: 注入标注回流引导
        if self.annotation_store:
            guidance = self.annotation_store.build_guidance_prompt(min_rating=4)
            if guidance:
                skill_context = f"{skill_context}\n\n{guidance}"

        # #11: 注入偏好画像
        if self.preference_profile:
            pref = self.preference_profile.get_preference("preferred_hook_style")
            if pref:
                skill_context = f"{skill_context}\n\n【用户偏好】hook_style={pref}"

        # 2. 构建 prompt
        prompt = self._build_prompt(skill_context, upstream_context, user_note, stage.input_data)

        # 3. 选择 provider（从已注册 provider 中选；传 previous_provider 让 continuity 评分生效）
        task_type = self.get_task_type()
        from ..providers.provider_registry import list_providers
        candidates = list_providers()
        if not candidates:
            raise RuntimeError("无可用 Provider，请配置环境变量（如 MINIMAX_API_KEY）")
        selection = self.provider_selector.select(
            task_type, candidates, previous_provider=state.last_provider or None
        )
        state.last_provider = selection.winner

        # 4. 调用 AI
        response = await self._call_ai(selection.winner, prompt)

        # 5. 解析输出
        output = self._parse_output(response)

        # #10: 统一用 confidence_scorer 计算置信度
        required_keys = get_required_keys(stage.name)
        confidence = calculate_confidence(output, required_keys)

        # 6. 记录决策
        self.decision_logger.log(
            stage=stage.name,
            provider=selection.winner,
            provider_score=selection.total_score,
            reasoning=selection.reasoning,
            confidence=confidence,
            output_summary=str(output)[:500],
        )

        return {"data": output, "confidence": confidence}

    @abstractmethod
    def get_task_type(self) -> TaskType:
        pass

    @abstractmethod
    def _build_prompt(self, skill_context: str, upstream_context: str,
                      user_note: str, input_data: dict) -> str:
        pass

    @abstractmethod
    def _parse_output(self, response: str) -> dict:
        pass

    def _build_upstream_context(self, state: ProjectState, stage: StageState) -> str:
        parts: list[str] = []
        for name, st in state.stages.items():
            if st.status == "completed" and st.output_data:
                summary = json.dumps(st.output_data, ensure_ascii=False)[:500]
                parts.append(f"[{name}] {summary}")
        return "\n".join(parts)

    async def _call_ai(self, provider_name: str, prompt: str) -> str:
        from ..providers.provider_registry import get_provider
        provider = get_provider(provider_name)
        return await provider.complete(prompt)

    def _extract_json(self, text: str) -> dict:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}
