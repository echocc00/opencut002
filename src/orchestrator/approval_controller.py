"""审批模式控制器 - 手动/半自动/全自动三种模式"""
from __future__ import annotations
from typing import Optional
from ..orchestrator.state import ProjectState, StageStatus


def should_pause_for_review(stage_type: str, approval_mode: str,
                            confidence: Optional[float] = None) -> bool:
    """根据审批模式和阶段类型决定是否暂停"""
    if approval_mode == "full_auto":
        return False
    if approval_mode == "manual":
        return stage_type in ("decision", "quality_gate", "manual")
    # semi_auto: decision类型高置信度自动通过
    if stage_type == "decision":
        if confidence is not None and confidence >= 80:
            return False
        return True
    if stage_type in ("quality_gate", "manual"):
        return True
    return False


def get_auto_retry_limit(approval_mode: str) -> int:
    """全自动模式下质量关卡不通过时的重试次数"""
    if approval_mode == "full_auto":
        return 3
    if approval_mode == "semi_auto":
        return 1
    return 0
