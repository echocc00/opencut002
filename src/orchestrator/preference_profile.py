"""用户偏好画像 - 记录用户决策历史，驱动自动模式"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any


class PreferenceProfile:
    def __init__(self, data_dir: Path, user_id: str = "default"):
        self.file_path = data_dir / "users" / f"{user_id}_profile.json"
        self.data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self.file_path.exists():
            return json.loads(self.file_path.read_text(encoding="utf-8"))
        return {
            "user_id": "default", "domain": "travel",
            "preferred_hook_style": "", "preferred_voice": "",
            "preferred_bgm_tempo": "", "preferred_pacing": "",
            "preferred_copywriting_tone": "",
            "rejected_topic_patterns": [],
            "approval_rate_by_stage": {},
            "total_videos_produced": 0,
            "last_updated": datetime.now().isoformat(),
        }

    def save(self):
        self.data["last_updated"] = datetime.now().isoformat()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def record_decision(self, stage: str, choice: Any, confidence: float = 0):
        """记录用户的一次决策"""
        decisions = self.data.setdefault("decisions", [])
        decisions.append({
            "stage": stage, "choice": str(choice),
            "confidence": confidence, "timestamp": datetime.now().isoformat(),
        })
        # 更新偏好统计
        if stage == "topic" and isinstance(choice, dict):
            directions = choice.get("directions", [])
            selected = choice.get("selected", -1)
            if directions and 0 <= selected < len(directions):
                hook = directions[selected].get("hook", "")
            elif directions:
                hook = directions[0].get("hook", "")
            else:
                hook = ""
            if hook:
                self.data["preferred_hook_style"] = hook
        elif stage == "voice_selection" and isinstance(choice, str):
            self.data["preferred_voice"] = choice
        self.data["total_videos_produced"] = self.data.get("total_videos_produced", 0) + 1
        self.save()

    def get_preference(self, key: str) -> Any:
        return self.data.get(key, "")

    def to_dict(self) -> dict[str, Any]:
        return self.data.copy()
