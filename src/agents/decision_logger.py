"""决策审计日志 - 每次 AI 调用留痕"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class DecisionLogger:
    def __init__(self, data_dir: Path, project_id: str):
        self.log_path = data_dir / "projects" / project_id / "decision_log.jsonl"

    def log(self, **kwargs: Any):
        # 支持的fields: stage, provider, provider_score, reasoning, confidence, output_summary, cost, tokens
        entry = {"timestamp": datetime.now().isoformat(), **kwargs}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_all(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        entries = []
        for line in self.log_path.read_text(encoding="utf-8").split("\n"):
            if line.strip():
                entries.append(json.loads(line))
        return entries

    def get_by_stage(self, stage_name: str) -> list[dict]:
        return [e for e in self.get_all() if e.get("stage") == stage_name]
