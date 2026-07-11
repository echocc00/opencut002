"""后置校验 - 检查阶段输出是否符合 schema"""
from __future__ import annotations

from typing import Any

from ..orchestrator.contracts import OUTPUT_CONTRACTS


def validate_output(stage_name: str, output: dict[str, Any]) -> tuple[bool, list[str]]:
    """验证阶段输出是否符合契约 schema"""
    issues: list[str] = []
    contract_cls = OUTPUT_CONTRACTS.get(stage_name)
    if contract_cls is None:
        return (True, [])  # 无契约定义的阶段跳过

    try:
        contract_cls.model_validate(output)
    except Exception as e:
        # 收集所有验证错误
        if hasattr(e, "errors"):
            for err in e.errors():
                loc = ".".join(str(x) for x in err.get("loc", []))
                msg = err.get("msg", "")
                issues.append(f"{loc}: {msg}")
        else:
            issues.append(str(e))

    return (len(issues) == 0, issues)


def check_output_completeness(stage_name: str, output: dict[str, Any]) -> tuple[bool, list[str]]:
    """检查输出是否为空或缺少关键内容"""
    issues: list[str] = []
    if not output:
        issues.append("输出为空")
        return (False, issues)

    # 阶段特定的完整性检查
    if stage_name == "copywriting":
        paragraphs = output.get("paragraphs", [])
        if not paragraphs:
            issues.append("文案段落为空")
        for i, p in enumerate(paragraphs):
            if not p.get("highlight_ref"):
                issues.append(f"段落 {i+1} 缺少 highlight_ref")
    elif stage_name == "storyboard":
        segments = output.get("segments", [])
        if not segments:
            issues.append("分镜段落数据为空")
    elif stage_name == "topic":
        directions = output.get("directions", [])
        if not directions:
            issues.append("选题方向为空")

    return (len(issues) == 0, issues)
