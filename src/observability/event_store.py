"""统一事件日志 - append-only JSONL，支持状态回放"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class EventStore:
    def __init__(self, data_dir: Path, project_id: str):
        self.log_path = data_dir / "projects" / project_id / "events.jsonl"

    def emit(self, event_type: str, **data: Any):
        """发射一个事件"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            **data,
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def emit_stage_started(self, stage: str, input_data: dict | None = None):
        self.emit("stage_started", stage=stage, input_data=input_data or {})

    def emit_stage_completed(self, stage: str, output_data: dict, confidence: float):
        self.emit("stage_completed", stage=stage, output_summary=str(output_data)[:500],
                  confidence=confidence)

    def emit_stage_error(self, stage: str, error: str):
        self.emit("stage_error", stage=stage, error=error)

    def emit_quality_gate(self, stage: str, passed: bool, score: float | None = None):
        self.emit("quality_gate", stage=stage, passed=passed, score=score)

    def emit_decision(self, stage: str, provider: str, score: float, reasoning: str):
        self.emit("decision", stage=stage, provider=provider, score=score, reasoning=reasoning)

    def emit_render(self, video_path: str, duration: float, passed: bool):
        self.emit("render", video_path=video_path, duration=duration, passed=passed)

    def get_all_events(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        events = []
        for line in self.log_path.read_text(encoding="utf-8").split("\n"):
            if line.strip():
                events.append(json.loads(line))
        return events

    def get_events_by_type(self, event_type: str) -> list[dict]:
        return [e for e in self.get_all_events() if e.get("type") == event_type]

    def replay(self) -> list[dict]:
        """回放全部事件（用于Replay Run功能）"""
        return self.get_all_events()
