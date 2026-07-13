"""幻灯片风险评分 - 6维度分析，防止"动画PPT"产出"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RiskScore:
    total_score: float = 0.0
    risk_level: str = "low"  # low / medium / high / critical
    passed: bool = True
    dimensions: dict[str, float] = field(default_factory=lambda: {
        "repetition": 0.0, "weak_motion": 0.0, "decorative_visuals": 0.0,
        "shot_intent": 0.0, "typography_overreliance": 0.0, "unsupported_cinematic": 0.0,
    })
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


WEIGHTS = {
    "repetition": 0.25, "weak_motion": 0.25, "decorative_visuals": 0.20,
    "shot_intent": 0.15, "typography_overreliance": 0.10, "unsupported_cinematic": 0.05,
}

THRESHOLDS = {"low": 0, "medium": 40, "high": 70, "critical": 85}


def score_storyboard(
    segments: list[dict[str, Any]],
    topic_data: dict[str, Any] | None = None,
    thresholds: dict[str, float] | None = None,
) -> RiskScore:
    """对分镜数据进行幻灯片风险评估。

    thresholds: 可选，覆盖默认 THRESHOLDS（如 {"high": 80, "critical": 90} 放宽阻断）。
                由 engine 从 domain style.yaml 的 quality_gates.slideshow_thresholds 注入，
                让运营不改代码即可调松/调紧质量关卡。
    """
    score = RiskScore()
    if not segments:
        score.total_score = 100.0
        score.risk_level = "critical"
        score.passed = False
        score.issues.append("无分镜数据")
        return score

    thr = {**THRESHOLDS, **(thresholds or {})}

    # 1. 重复度 (25%)
    score.dimensions["repetition"] = _score_repetition(segments)

    # 2. 弱动态 (25%)
    score.dimensions["weak_motion"] = _score_weak_motion(segments)

    # 3. 装饰性画面 (20%) - 简化版：检查是否有 image 为空
    score.dimensions["decorative_visuals"] = _score_decorative(segments)

    # 4. 镜头意图 (15%)
    score.dimensions["shot_intent"] = _score_shot_intent(segments)

    # 5. 排版过度依赖 (10%)
    score.dimensions["typography_overreliance"] = _score_typography(segments)

    # 6. 不支持的 cinematic 声明 (5%)
    score.dimensions["unsupported_cinematic"] = _score_cinematic(segments, topic_data)

    score.total_score = sum(score.dimensions[d] * w for d, w in WEIGHTS.items())

    if score.total_score >= thr["critical"]:
        score.risk_level = "critical"
        score.passed = False
    elif score.total_score >= thr["high"]:
        score.risk_level = "high"
        score.passed = False
    elif score.total_score >= thr["medium"]:
        score.risk_level = "medium"
    else:
        score.risk_level = "low"

    _generate_suggestions(score)
    return score


def _score_repetition(segments: list[dict]) -> float:
    total = len(segments)
    consecutive_repeats = 0
    for i in range(1, total):
        if segments[i].get("image") == segments[i-1].get("image") and segments[i].get("image"):
            consecutive_repeats += 1
    repeat_ratio = consecutive_repeats / max(total - 1, 1)
    score = repeat_ratio * 60

    unique_images = len(set(s.get("image", "") for s in segments if s.get("image")))
    variety = unique_images / max(total, 1)
    if variety < 0.5:
        score += (0.5 - variety) * 80
    return min(score, 100.0)


def _score_weak_motion(segments: list[dict]) -> float:
    total = len(segments)
    static_count = sum(1 for s in segments if not s.get("ab_split", False))
    static_ratio = static_count / max(total, 1)
    score = static_ratio * 50

    # 分位数阈值：超过4.5秒才开始罚分，5.5秒满分罚分
    durations = [s.get("actual_duration", 3.0) for s in segments]
    avg_dur = sum(durations) / max(len(durations), 1) if durations else 0
    if avg_dur > 5.5:
        score += 50  # 满分罚分
    elif avg_dur > 4.5:
        # 4.5-5.5之间平滑过渡
        score += 50 * (avg_dur - 4.5) / 1.0
    return min(score, 100.0)


def _score_decorative(segments: list[dict]) -> float:
    no_image = sum(1 for s in segments if not s.get("image"))
    return (no_image / max(len(segments), 1)) * 100


def _score_shot_intent(segments: list[dict]) -> float:
    # 简化版：检查时长是否有变化
    durations = [round(s.get("actual_duration", 3.0), 1) for s in segments]
    if len(set(durations)) > 1:
        return 0.0
    return 60.0


def _score_typography(segments: list[dict]) -> float:
    text_heavy = 0
    for s in segments:
        subtitle = s.get("subtitle", "")
        if len(subtitle) > 50 and not s.get("image"):
            text_heavy += 1
    return (text_heavy / max(len(segments), 1)) * 100


def _score_cinematic(segments: list[dict], topic_data: dict | None) -> float:
    if not topic_data:
        return 0.0
    selected = topic_data.get("selected", -1)
    directions = topic_data.get("directions", [])
    if 0 <= selected < len(directions):
        hook = str(directions[selected].get("hook", "")).lower()
        cinematic_kw = ["cinematic", "电影感", "大片", "trailer"]
        if any(kw in hook for kw in cinematic_kw):
            has_motion = any(s.get("ab_split") for s in segments)
            if not has_motion:
                return 80.0
    return 0.0


def _generate_suggestions(score: RiskScore):
    labels = {
        "repetition": "画面重复度过高：建议为连续段落使用不同图片，或启用 A/B Split 双画面模式",
        "weak_motion": "动态感不足：建议增加 Ken Burns 效果参数变化，或使用更多 A/B Split 段落",
        "decorative_visuals": "画面与内容匹配度低：建议重新运行画面匹配阶段，或手动调整图片分配",
        "typography_overreliance": "纯文字段落过多：建议为长字幕段落添加辅助画面，或拆分为更短的段落",
        "shot_intent": "镜头语言单一：建议在分镜中交替使用不同景别（特写/中景/全景）",
        "unsupported_cinematic": "cinematic 声明缺乏支撑：建议添加更多动态镜头或降低 cinematic 预期",
    }
    for dim, s in score.dimensions.items():
        if s > 50 and dim in labels:
            score.suggestions.append(labels[dim])
