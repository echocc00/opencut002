"""置信度评分系统 - 规则评分 + AI自评加权"""
from __future__ import annotations
from typing import Any


def calculate_confidence(output: dict[str, Any], required_keys: list[str] | None = None,
                         ai_self_score: float | None = None) -> float:
    """计算置信度分数 (0-100)

    评分逻辑：
    - 规则评分 (60%权重)：字段完整度 + 非空率 + 结构性指标
    - AI自评 (40%权重)：如果提供ai_self_score
    """
    if not output:
        return 20.0

    # === 规则评分 ===
    rule_score = 40.0  # 基础分

    # 必填字段检查
    if required_keys:
        has_all = all(k in output for k in required_keys)
        if has_all:
            rule_score += 20
        else:
            rule_score -= 10

    # 字段值非空
    non_empty = sum(1 for v in output.values() if v)
    total = len(output)
    if total > 0 and non_empty / total > 0.7:
        rule_score += 10

    # 输出项数
    if len(output) >= 3:
        rule_score += 5

    # 结构性指标
    rule_score += _structural_metrics(output)

    rule_score = min(max(rule_score, 0.0), 100.0)

    # === 加权 ===
    if ai_self_score is not None:
        return min(0.6 * rule_score + 0.4 * ai_self_score, 100.0)
    return rule_score


def _structural_metrics(output: dict[str, Any]) -> float:
    """结构性指标加分/扣分"""
    bonus = 0.0

    # 文案段落长度方差检查（不能3字+80字交替）
    if "paragraphs" in output:
        paras = output["paragraphs"]
        if paras and len(paras) > 1:
            lengths = [len(p.get("text", "")) for p in paras]
            avg = sum(lengths) / len(lengths)
            variance = sum((l - avg) ** 2 for l in lengths) / len(lengths)
            if variance > 500:  # 方差过大
                bonus -= 10
            else:
                bonus += 5

    # highlight_ref 引用闭合检查
    if "paragraphs" in output:
        refs = [p.get("highlight_ref", "") for p in output.get("paragraphs", [])]
        empty_refs = sum(1 for r in refs if not r)
        if empty_refs > 0:
            bonus -= 5 * empty_refs

    # 时间戳连续性检查
    if "segments" in output:
        segs = output.get("segments", [])
        for i in range(1, len(segs)):
            prev_end = segs[i-1].get("time_start", 0) + segs[i-1].get("actual_duration", 0)
            curr_start = segs[i].get("time_start", 0)
            if curr_start < prev_end - 0.1:  # 时间回退
                bonus -= 10
                break

    return bonus


# 各阶段的必填字段
STAGE_REQUIRED_KEYS: dict[str, list[str]] = {
    "topic": ["directions"],
    "highlight_selection": ["options"],
    "copywriting": ["paragraphs"],
    "storyboard": ["segments"],
    "bgm": ["candidates"],
    "title": ["titles"],
}


def get_required_keys(stage_name: str) -> list[str] | None:
    return STAGE_REQUIRED_KEYS.get(stage_name)


# AI自评prompt模板（注入到各Agent的prompt末尾）
AI_SELF_EVAL_PROMPT = """
请在JSON输出的最后附带 "confidence": 0-100的整数，表示你对这次输出的自信度：
- 字段完整性: 0=缺字段, 100=全字段
- 推理可靠性: 0=猜测, 100=基于上游证据
- 创意稳健性: 0=违反多项反模式, 100=完全符合技能文件
"""
