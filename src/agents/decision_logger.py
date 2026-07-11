"""决策审计日志 - 每次 AI 调用留痕

R12: 与 EventStore 合并，统一写入 events.jsonl（type="decision"）。
旧 decision_log.jsonl 只读兼容（events.jsonl 无决策事件时回退读取）。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class DecisionLogger:
    def __init__(self, data_dir: Path, project_id: str):
        self.log_path = data_dir / "projects" / project_id / "events.jsonl"
        self._legacy_path = data_dir / "projects" / project_id / "decision_log.jsonl"

    def log(self, **kwargs: Any):
        """记录一条决策事件到 events.jsonl（与 EventStore 统一）"""
        event = {"timestamp": datetime.now().isoformat(), "type": "decision", **kwargs}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _read_decisions(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        entries: list[dict] = []
        for line in path.read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            # events.jsonl 有 type 字段，只取 decision；旧 decision_log.jsonl 无 type，默认视为 decision
            if e.get("type", "decision") == "decision":
                entries.append(e)
        return entries

    def get_all(self) -> list[dict]:
        decisions = self._read_decisions(self.log_path)
        if not decisions and self._legacy_path.exists():
            # 回退读旧 decision_log.jsonl（只读兼容期）
            decisions = self._read_decisions(self._legacy_path)
        return decisions

    def get_by_stage(self, stage_name: str) -> list[dict]:
        return [e for e in self.get_all() if e.get("stage") == stage_name]
