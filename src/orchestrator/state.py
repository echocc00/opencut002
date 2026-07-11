"""模块化项目状态管理 - 替代 v2 单体 ProjectState"""
from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


class StageStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    ERROR = "error"


class StageState(BaseModel):
    """单个阶段的状态"""
    name: str
    status: StageStatus = StageStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    confidence_score: Optional[float] = None
    retry_count: int = 0


class ProjectState(BaseModel):
    """项目全局状态"""
    project_id: str
    domain: str = "travel"
    approval_mode: str = "manual"
    mode: str = "material"  # material / reference
    reference_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    materials: list[dict[str, Any]] = Field(default_factory=list)
    stages: dict[str, StageState] = Field(default_factory=dict)
    user_notes: dict[str, str] = Field(default_factory=dict)
    quality_reports: list[dict[str, Any]] = Field(default_factory=list)
    decision_log_path: Optional[str] = None
    cost_total: float = 0.0
    last_provider: str = ""

    def get_stage(self, name: str) -> StageState:
        if name not in self.stages:
            self.stages[name] = StageState(name=name)
        return self.stages[name]

    def mark_stage(self, name: str, status: StageStatus):
        stage = self.get_stage(name)
        stage.status = status
        if status == StageStatus.IN_PROGRESS and stage.started_at is None:
            stage.started_at = datetime.now()
        if status == StageStatus.COMPLETED:
            stage.completed_at = datetime.now()

    def is_stage_completed(self, name: str) -> bool:
        stage = self.stages.get(name)
        return stage is not None and stage.status == StageStatus.COMPLETED

    def get_stage_output(self, name: str) -> dict[str, Any]:
        stage = self.stages.get(name)
        return stage.output_data if stage else {}

    def save(self, data_dir: Path):
        path = data_dir / "projects" / self.project_id / "state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, data_dir: Path, project_id: str) -> Optional[ProjectState]:
        path = data_dir / "projects" / project_id / "state.json"
        if path.exists():
            return cls.model_validate_json(path.read_text(encoding="utf-8"))
        return None
