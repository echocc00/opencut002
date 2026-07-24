"""项目操作 API - 创建/启动/审批/查状态/列表（v0.4.0 加 auth + ownership + DB 元数据）"""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db.engine import get_session
from ..db.models import Project, User
from ..orchestrator.engine import PipelineEngine
from ..orchestrator.state import ProjectState
from ..tools.material_prep import prepare_materials
from .auth import get_current_user
from .job_runner import start_job_for_project

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _get_data_dir() -> Path:
    return get_settings().data_dir


async def _check_project_owner(session: AsyncSession, project_id: str, user: User) -> Project:
    """查 Project DB 行并校验 ownership，返回 Project"""
    result = await session.execute(select(Project).where(Project.project_id == project_id))
    project = result.scalar_one_or_none()
    if project is None or project.user_id != user.id:
        raise HTTPException(404, "项目不存在或无权访问")
    return project


@router.get("")
async def list_projects(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """列出当前用户的项目"""
    result = await session.execute(
        select(Project).where(Project.user_id == user.id).order_by(Project.created_at.desc())
    )
    return [
        {"project_id": p.project_id, "domain": p.domain,
         "approval_mode": p.approval_mode, "created_at": p.created_at}
        for p in result.scalars()
    ]


@router.post("/create")
async def create_project(
    domain: str = Form("travel"),
    approval_mode: str = Form("full_auto"),
    materials: list[UploadFile] = File(default=[]),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """创建新项目并上传素材（支持图片 + 视频，自动抽帧）"""
    import uuid
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    data_dir = _get_data_dir()
    proj_dir = data_dir / "projects" / project_id
    mat_dir = proj_dir / "materials"
    mat_dir.mkdir(parents=True, exist_ok=True)

    for f in materials:
        dest = mat_dir / (f.filename or "upload")
        with open(dest, "wb") as out:
            shutil.copyfileobj(f.file, out)

    # prepare_materials：收集图片 + 视频抽帧（OPENCUT_MATERIAL_DIVERSITY=1 时帧间差异选帧，v0.6.4）
    from ..tools.material_prep import DIVERSITY_MAX_PER_VIDEO, diversity_enabled
    _div = diversity_enabled()
    prepared = prepare_materials(
        mat_dir,
        max_per_video=DIVERSITY_MAX_PER_VIDEO if _div else None,
        diversity=_div,
    )
    if not prepared:
        raise HTTPException(400, "未提供可用素材（支持 jpg/jpeg/png 图片或 mp4 等视频）")

    state = ProjectState(
        project_id=project_id, domain=domain,
        approval_mode=approval_mode, materials=prepared,
    )
    state.save(data_dir)

    # DB 元数据
    project = Project(project_id=project_id, user_id=user.id,
                      domain=domain, approval_mode=approval_mode)
    session.add(project)
    await session.commit()

    return {"project_id": project_id, "materials_count": len(prepared),
            "domain": domain, "approval_mode": approval_mode}


@router.post("/{project_id}/run")
async def run_pipeline(
    project_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """启动/恢复管道执行（创建 Job + 入线程池）"""
    job = await start_job_for_project(session, project_id, user)
    return {"project_id": project_id, "job_id": job.id, "status": "queued"}


@router.post("/{project_id}/approve/{stage_name}")
async def approve_stage(
    project_id: str,
    stage_name: str,
    approved: bool = Form(True),
    feedback: str = Form(""),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """审批一个处于 REVIEW 状态的阶段（同步执行恢复，MVP 简化）"""
    await _check_project_owner(session, project_id, user)
    data_dir = _get_data_dir()
    state = ProjectState.load(data_dir, project_id)
    if not state:
        raise HTTPException(404, "Project state not found")

    from ..agents.skill_loader import SkillLoader
    from ..agents.decision_logger import DecisionLogger
    from ..providers.selector import ProviderSelector
    from ..config import DomainConfig
    eng = PipelineEngine(data_dir=data_dir)
    config = DomainConfig(get_settings().domains_dir / state.domain)
    logger = DecisionLogger(data_dir, project_id)
    eng.auto_register_handlers(SkillLoader(config), ProviderSelector(), logger)
    await eng.approve_stage(state, stage_name, approved, feedback)
    return {"project_id": project_id, "stage": stage_name,
            "approved": approved, "state": state.get_stage(stage_name).status}


@router.get("/{project_id}/state")
async def get_state(
    project_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """获取完整项目状态（含各阶段进度，供前端轮询）"""
    await _check_project_owner(session, project_id, user)
    data_dir = _get_data_dir()
    state = ProjectState.load(data_dir, project_id)
    if not state:
        raise HTTPException(404, "Project state not found")
    return state.model_dump()
