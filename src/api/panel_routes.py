"""生产监控面板 API"""
from __future__ import annotations
import json
from pathlib import Path
from fastapi import APIRouter

router = APIRouter(prefix="/api/panel", tags=["panel"])


@router.get("/{project_id}/status")
async def get_project_status(project_id: str):
    """获取项目管道状态"""
    from ..config import get_settings
    state_path = get_settings().data_dir / "projects" / project_id / "state.json"
    if not state_path.exists():
        return {"error": "project not found"}
    state = json.loads(state_path.read_text(encoding="utf-8"))

    stages = []
    for name, stage in state.get("stages", {}).items():
        stages.append({
            "name": name, "status": stage.get("status"),
            "started_at": stage.get("started_at"),
            "completed_at": stage.get("completed_at"),
            "confidence": stage.get("confidence_score"),
        })
    return {
        "project_id": project_id, "domain": state.get("domain"),
        "approval_mode": state.get("approval_mode"),
        "stages": stages, "cost_total": state.get("cost_total", 0),
    }


@router.get("/{project_id}/decisions")
async def get_decision_log(project_id: str):
    """获取决策审计日志"""
    log_path = get_settings().data_dir / "projects" / project_id / "decision_log.jsonl"
    if not log_path.exists():
        return {"decisions": []}
    decisions = []
    for line in log_path.read_text(encoding="utf-8").split("\n"):
        if line.strip():
            decisions.append(json.loads(line))
    return {"decisions": decisions}


@router.get("/{project_id}/quality")
async def get_quality_reports(project_id: str):
    """获取质量报告"""
    from ..config import get_settings
    state_path = get_settings().data_dir / "projects" / project_id / "state.json"
    if not state_path.exists():
        return {"reports": []}
    state = json.loads(state_path.read_text(encoding="utf-8"))
    return {"reports": state.get("quality_reports", [])}
