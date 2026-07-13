"""项目操作 API - 创建/启动/审批/上传素材"""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks

from ..orchestrator.state import ProjectState, StageStatus
from ..orchestrator.engine import PipelineEngine
from ..agents.skill_loader import SkillLoader
from ..agents.decision_logger import DecisionLogger
from ..providers.selector import ProviderSelector
from ..config import DomainConfig, get_settings

router = APIRouter(prefix="/api/projects", tags=["projects"])

_running_projects: set[str] = set()


def _get_data_dir() -> Path:
    return get_settings().data_dir


@router.post("/create")
async def create_project(
    domain: str = Form("travel"),
    approval_mode: str = Form("manual"),
    materials: list[UploadFile] = File(default=[]),
):
    """创建新项目并上传素材"""
    import uuid
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    data_dir = _get_data_dir()

    # 创建项目目录
    proj_dir = data_dir / "projects" / project_id
    mat_dir = proj_dir / "materials"
    mat_dir.mkdir(parents=True, exist_ok=True)

    # 保存上传的素材
    saved_materials = []
    for f in materials:
        dest = mat_dir / f.filename
        with open(dest, "wb") as out:
            shutil.copyfileobj(f.file, out)
        saved_materials.append({"file": str(dest), "filename": f.filename})

    # 创建初始状态
    state = ProjectState(
        project_id=project_id,
        domain=domain,
        approval_mode=approval_mode,
        materials=saved_materials,
    )
    state.save(data_dir)

    return {"project_id": project_id, "materials_count": len(saved_materials),
            "domain": domain, "approval_mode": approval_mode}


@router.post("/{project_id}/run")
async def run_pipeline(project_id: str, approval_mode: str = Form(None), bg_tasks: BackgroundTasks = None):
    """启动/恢复管道执行"""
    data_dir = _get_data_dir()
    state = ProjectState.load(data_dir, project_id)
    if not state:
        raise HTTPException(404, "Project not found")

    if approval_mode:
        state.approval_mode = approval_mode

    # 初始化引擎并自动注册handler
    eng = PipelineEngine(data_dir=data_dir)
    config = DomainConfig(get_settings().domains_dir / state.domain)
    loader = SkillLoader(config)
    selector = ProviderSelector()
    logger = DecisionLogger(data_dir, project_id)

    # 注入偏好画像和标注回流
    from ..orchestrator.preference_profile import PreferenceProfile
    from ..observability.annotation_store import AnnotationStore
    profile = PreferenceProfile(data_dir, "default")
    store = AnnotationStore(data_dir)

    eng.auto_register_handlers(loader, selector, logger,
                               preference_profile=profile,
                               annotation_store=store)

    # 注入material_analysis的输入数据
    ma_stage = state.get_stage("material_analysis")
    ma_stage.input_data = {"materials": state.materials}

    # 并发控制
    if project_id in _running_projects:
        raise HTTPException(409, "Pipeline already running for this project")
    _running_projects.add(project_id)

    async def _run_and_cleanup():
        try:
            await eng.run(state)
        finally:
            _running_projects.discard(project_id)

    # 异步执行（使用BackgroundTasks，进程崩溃时task不丢失）
    if bg_tasks:
        bg_tasks.add_task(_run_and_cleanup)
    else:
        asyncio.create_task(_run_and_cleanup())

    return {"project_id": project_id, "status": "running",
            "approval_mode": state.approval_mode}


@router.post("/{project_id}/approve/{stage_name}")
async def approve_stage(
    project_id: str,
    stage_name: str,
    approved: bool = Form(True),
    feedback: str = Form(""),
):
    """审批一个处于REVIEW状态的阶段"""
    data_dir = _get_data_dir()
    state = ProjectState.load(data_dir, project_id)
    if not state:
        raise HTTPException(404, "Project not found")

    eng = PipelineEngine(data_dir=data_dir)
    config = DomainConfig(get_settings().domains_dir / state.domain)
    loader = SkillLoader(config)
    selector = ProviderSelector()
    logger = DecisionLogger(data_dir, project_id)
    from ..orchestrator.preference_profile import PreferenceProfile
    from ..observability.annotation_store import AnnotationStore
    profile = PreferenceProfile(data_dir, 'default')
    store = AnnotationStore(data_dir)
    eng.auto_register_handlers(loader, selector, logger,
                               preference_profile=profile, annotation_store=store)

    await eng.approve_stage(state, stage_name, approved, feedback)

    return {"project_id": project_id, "stage": stage_name,
            "approved": approved, "state": state.get_stage(stage_name).status}


@router.get("/{project_id}/state")
async def get_state(project_id: str):
    """获取完整项目状态"""
    data_dir = _get_data_dir()
    state = ProjectState.load(data_dir, project_id)
    if not state:
        raise HTTPException(404, "Project not found")
    return state.model_dump()
