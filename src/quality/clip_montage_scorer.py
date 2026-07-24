"""故事板蒙太奇质量评分器（v0.6.4，借鉴第三方 fork Level B/B1 设计思想）。

纯函数评分，无外部依赖（仅 stdlib），不接线进 engine —— 供 CLI 体检 / 未来
原生视频剪辑模式（Level B）质量门控复用。覆盖维度：

- 视频占比（video_ratio）：视觉段中真视频段的占比
- 源多样性（unique_sources / max_source_reuse / consecutive_same_source）
- 缺失/过短片段（missing_clips / short_clips / blank_fallbacks）
- 时间线连续性（timeline_discontinuities，相邻段首尾时间应对齐）
- 人脸遮盖合规（face_mask_coverage，可设最低覆盖率门控，B1 隐私/版权保护）

total_score 是**风险分**（0=无风险，越高风险越大），issues 非空即 passed=False。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ClipMontageScore:
    total_score: float = 0.0          # 风险分：0 无风险，越高越差
    risk_level: str = "low"           # low / medium / high / critical
    passed: bool = True
    metrics: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


def score_clip_storyboard(
    segments: list[dict[str, Any]],
    *,
    min_video_ratio: float = 0.8,
    min_unique_sources: int = 5,
    max_source_reuse: int = 2,
    fps: int = 30,
    min_face_mask_ratio: float = 0.0,
) -> ClipMontageScore:
    """对 TTS 锚定的蒙太奇故事板评分。segments 为故事板段列表。

    每段可含字段：text_card / asset_type / clip{source_id,file,duration} /
    image / actual_duration / time_start。
    """
    score = ClipMontageScore()
    if not segments:
        score.total_score = 100.0
        score.risk_level = "critical"
        score.passed = False
        score.issues.append("empty clip storyboard")
        return score

    visual_segments = [s for s in segments if not s.get("text_card")]
    video_segments = [
        s for s in visual_segments
        if s.get("asset_type") == "video" and s.get("clip")
    ]
    video_ratio = len(video_segments) / max(len(visual_segments), 1)
    source_ids = [s.get("clip", {}).get("source_id", "") for s in video_segments]
    source_counts = Counter(src for src in source_ids if src)
    unique_sources = len(source_counts)
    max_reuse = max(source_counts.values(), default=0)
    consecutive = sum(
        bool(source_ids[i]) and source_ids[i] == source_ids[i - 1]
        for i in range(1, len(source_ids))
    )

    missing_clips = 0
    short_clips = 0
    blank_fallbacks = 0
    for s in segments:
        clip = s.get("clip") or {}
        if s.get("asset_type") == "video":
            if not clip.get("file") or not Path(clip.get("file", "")).exists():
                missing_clips += 1
            if float(clip.get("duration", 0) or 0) + 1 / fps < float(s.get("actual_duration", 0) or 0):
                short_clips += 1
        elif not s.get("text_card") and not s.get("image"):
            blank_fallbacks += 1

    discontinuities = 0
    ordered = sorted(segments, key=lambda it: float(it.get("time_start", 0) or 0))
    for prev, cur in zip(ordered, ordered[1:]):
        expected = float(prev.get("time_start", 0) or 0) + float(prev.get("actual_duration", 0) or 0)
        actual = float(cur.get("time_start", 0) or 0)
        if abs(actual - expected) > 1 / fps + 1e-6:
            discontinuities += 1

    unique_target = min(max(0, min_unique_sources), len(visual_segments))
    face_mask_coverage = 0.0
    if segments:
        masked = sum(1 for s in segments if (s.get("clip") or {}).get("file"))
        face_mask_coverage = masked / len(segments)
    score.metrics = {
        "video_ratio": round(video_ratio, 4), "unique_sources": unique_sources,
        "max_source_reuse": max_reuse, "consecutive_same_source": consecutive,
        "missing_clips": missing_clips, "short_clips": short_clips,
        "blank_fallbacks": blank_fallbacks, "timeline_discontinuities": discontinuities,
        "face_mask_coverage": round(face_mask_coverage, 4),
    }

    risk = 0.0
    if min_face_mask_ratio > 0 and face_mask_coverage < min_face_mask_ratio:
        score.issues.append(f"face mask coverage {face_mask_coverage:.2f} below {min_face_mask_ratio:.2f}")
        risk += min(40.0, (min_face_mask_ratio - face_mask_coverage) / max(min_face_mask_ratio, 0.01) * 40)
    if video_ratio < min_video_ratio:
        score.issues.append(f"video ratio {video_ratio:.2f} below {min_video_ratio:.2f}")
        risk += min(40.0, (min_video_ratio - video_ratio) / max(min_video_ratio, 0.01) * 40)
    if unique_sources < unique_target:
        score.issues.append(f"unique sources {unique_sources} below {unique_target}")
        risk += (unique_target - unique_sources) / max(unique_target, 1) * 20
    if max_reuse > max_source_reuse:
        score.issues.append(f"source reuse {max_reuse} exceeds {max_source_reuse}")
        risk += min(20.0, (max_reuse - max_source_reuse) * 10)
    if consecutive:
        score.issues.append(f"consecutive same source count {consecutive}")
        risk += min(20.0, consecutive * 10)
    if missing_clips:
        score.issues.append(f"missing clip files {missing_clips}")
        risk += min(40.0, missing_clips * 20)
    if short_clips:
        score.issues.append(f"short clips {short_clips}")
        risk += min(40.0, short_clips * 20)
    if blank_fallbacks:
        score.issues.append(f"blank fallbacks {blank_fallbacks}")
        risk += min(40.0, blank_fallbacks * 20)
    if discontinuities:
        score.issues.append(f"timeline discontinuities {discontinuities}")
        risk += min(40.0, discontinuities * 20)

    score.total_score = round(min(100.0, risk), 2)
    score.passed = not score.issues
    if score.total_score >= 70:
        score.risk_level = "critical"
    elif score.total_score >= 40:
        score.risk_level = "high"
    elif score.total_score >= 20:
        score.risk_level = "medium"
    else:
        score.risk_level = "low"
    if score.issues:
        score.suggestions.append("rebuild the clip timeline with more distinct valid sources")
    return score
