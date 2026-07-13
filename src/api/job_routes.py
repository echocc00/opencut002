"""任务路由：GET /api/jobs/{id}（状态）, GET /api/jobs（列表）, GET /api/jobs/{id}/result（下载）。

启动任务统一走 start_job_for_project（被 /api/jobs 和 /api/projects/{id}/run 复用）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.engine import get_session
from ..db.models import Job, Project, User
from .auth import get_current_user
from .job_runner import start_job_for_project

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("")
async def create_job(
    project_id: str = Query(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """启动任务：校验 ownership + 注册 providers + 建 Job 行 + 入线程池"""
    job = await start_job_for_project(session, project_id, user)
    return {"job_id": job.id, "project_id": project_id, "status": "queued"}


@router.get("/{job_id}")
async def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    job = await session.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(404, "任务不存在或无权访问")
    return {
        "id": job.id, "status": job.status, "current_stage": job.current_stage,
        "stages_total": job.stages_total, "stages_completed": job.stages_completed,
        "error": job.error, "video_path": job.video_path,
        "created_at": job.created_at, "started_at": job.started_at,
        "completed_at": job.completed_at,
    }


@router.get("")
async def list_jobs(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    project_id: str | None = Query(None),
):
    """列用户任务，可按 project_id 过滤"""
    stmt = select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc())
    if project_id:
        stmt = stmt.join(Project, Job.project_id == Project.id).where(
            Project.project_id == project_id)
    result = await session.execute(stmt)
    return [
        {"id": j.id, "status": j.status, "current_stage": j.current_stage,
         "stages_completed": j.stages_completed, "stages_total": j.stages_total,
         "created_at": j.created_at, "completed_at": j.completed_at}
        for j in result.scalars()
    ]


@router.get("/{job_id}/result")
async def download_result(
    job_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    job = await session.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(404, "任务不存在或无权访问")
    if job.status != "completed" or not job.video_path:
        raise HTTPException(409, "任务未完成或无视频产出")
    path = Path(job.video_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise HTTPException(404, "视频文件不存在")
    return FileResponse(str(path), media_type="video/mp4", filename="final.mp4")
