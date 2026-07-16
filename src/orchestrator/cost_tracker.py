"""成本预算闸（v0.6.2）。

ProjectState.budget_usd 设上限（美元），engine 每阶段执行前 check_budget，
超限 raise BudgetExceeded -> engine 中止管道（防 API 失控烧钱）。

budget_usd=0 = 不限（默认，零行为变化）。
estimated_usd 难以执行前精确预估，当前传 0：闸在成本累积后于后续阶段触发（post-hoc，
fail-safe）。未来可按 provider runtime + max_tokens 粗估。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import ProjectState


class BudgetExceeded(Exception):
    """预算超限。engine 捕获后标阶段 ERROR + 中止管道。"""

    def __init__(self, stage: str, cost_total: float, estimated: float, budget: float):
        self.stage = stage
        self.cost_total = cost_total
        self.estimated = estimated
        self.budget = budget
        super().__init__(
            f"阶段 '{stage}' 预算超限：已花 {cost_total:.4f} + 预估 {estimated:.4f} > 上限 {budget:.4f} USD"
        )


class CostTracker:
    @staticmethod
    def check_budget(state: "ProjectState", estimated_usd: float = 0.0,
                     stage_name: str = "") -> bool:
        """预算内返 True；超限 raise BudgetExceeded。budget_usd<=0 不限。"""
        if state.budget_usd <= 0:
            return True
        projected = state.cost_total + estimated_usd
        if projected > state.budget_usd:
            raise BudgetExceeded(stage_name, state.cost_total, estimated_usd, state.budget_usd)
        return True
