"""标注回流系统 - 发布后标注质量维度，下次AI读取作为引导"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any


POSITIVE_TAGS = [
    "opening_grabbing", "bgm_matching", "transition_smooth",
    "copywriting_engaging", "highlight_visible", "pacing_good",
]
NEGATIVE_TAGS = [
    "opening_weak", "bgm_mismatch", "transition_abrupt",
    "copywriting_flat", "highlight_missing", "pacing_drag",
]


class AnnotationStore:
    def __init__(self, data_dir: Path):
        self.file_path = data_dir / "annotations.json"

    def add_annotation(self, video_id: str, project_name: str,
                       positive_tags: list[str], negative_tags: list[str],
                       overall_rating: int = 0, notes: str = "") -> dict:
        """添加一条视频标注"""
        annotations = self._load()
        annotation = {
            "video_id": video_id, "project_name": project_name,
            "positive_tags": positive_tags, "negative_tags": negative_tags,
            "overall_rating": overall_rating, "notes": notes,
            "annotated_at": datetime.now().isoformat(),
        }
        annotations[video_id] = annotation
        self._save(annotations)
        return annotation

    def get_top_rated(self, min_rating: int = 4, limit: int = 20) -> list[dict]:
        """获取高评分视频"""
        annotations = self._load()
        return sorted(
            [a for a in annotations.values() if a.get("overall_rating", 0) >= min_rating],
            key=lambda a: a.get("overall_rating", 0), reverse=True,
        )[:limit]

    def get_positive_tags_summary(self, min_rating: int = 4) -> dict[str, int]:
        """获取高评分视频的正向标签统计"""
        top = self.get_top_rated(min_rating)
        tag_counts: dict[str, int] = {}
        for v in top:
            for tag in v.get("positive_tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return tag_counts

    def build_guidance_prompt(self, min_rating: int = 4) -> str:
        """构建可注入AI prompt的正向引导文本"""
        tags = self.get_positive_tags_summary(min_rating)
        if not tags:
            return ""
        labels = {
            "opening_grabbing": "开头抓人", "bgm_matching": "BGM踩点准",
            "transition_smooth": "转场流畅", "copywriting_engaging": "文案有感染力",
            "highlight_visible": "亮点体现到位", "pacing_good": "节奏感好",
        }
        parts = ["【历史高评分视频特征 - 请参考】"]
        for tag, count in sorted(tags.items(), key=lambda x: -x[1]):
            parts.append(f"- {labels.get(tag, tag)}（{count}条视频的共同特征）")
        return "\n".join(parts)

    def _load(self) -> dict[str, Any]:
        if self.file_path.exists():
            return json.loads(self.file_path.read_text(encoding="utf-8"))
        return {}

    def _save(self, data: dict):
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
