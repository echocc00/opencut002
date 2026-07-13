"""异步任务运行器：线程池跑 PipelineEngine，用 sync session 写 Job 状态。

MVP 无 Celery/Redis：进程重启丢运行中任务（queued/failed 在 DB 保留）。prod 用 Celery+Redis。
阻塞的 subprocess（ffmpeg/Remotion）在线程跑，不卡 FastAPI event loop。
Job 状态更新用 sync engine（SQLite WAL 允许 async 读 + sync 写并发），避免跨 loop 协调。
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from sqlalchemy import select

from ..agents.decision_logger import DecisionLogger
from ..agents.skill_loader import SkillLoader
from ..config import DomainConfig, get_settings
from ..db.engine import get_sync_session_factory
from ..db.models import Job, Project, User
from ..orchestrator.engine import PipelineEngine
from ..orchestrator.state import ProjectState
from ..providers.provider_registry import auto_register_all
from ..providers.selector import ProviderSelector

log = logging.getLogger(__name__)


class JobRunner:
    def __init__(self, max_workers: int = 2):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def start_job(self, job_id: int, project_id: str) -> None:
        self.executor.submit(self._run_in_thread, job_id, project_id)

    def _run_in_thread(self, job_id: int, project_id: str) -> None:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._run_job(job_id, project_id))
        except Exception:
            log.exception("Job %s 线程异常", job_id)
        finally:
            loop.close()

    async def _run_job(self, job_id: int, project_id: str) -> None:
        self._update_job(job_id, status="running", started_at=datetime.utcnow())
        try:
            data_dir = get_settings().data_dir
            state = ProjectState.load(data_dir, project_id)
            if state is None:
                raise RuntimeError(f"ProjectState {project_id} 不存在")

            eng = PipelineEngine(data_dir=data_dir)
            config = DomainConfig(get_settings().domains_dir / state.domain)
            logger = DecisionLogger(data_dir, project_id)
            eng.auto_register_handlers(SkillLoader(config), ProviderSelector(), logger)
            state.get_stage("material_analysis").input_data = {"materials": state.materials}

            stages_total = len(eng.get_stages())
            completed = {"n": 0}

            def on_stage_start(name: str) -> None:
                completed["n"] += 1
                self._update_job(job_id, current_stage=name,
                                 stages_total=stages_total, stages_completed=completed["n"])

            await eng.run(state, on_stage_start=on_stage_start)

            render_out = state.get_stage_output("render") or {}
            video_path = render_out.get("video_path", "") if isinstance(render_out, dict) else ""
            self._update_job(job_id, status="completed", video_path=video_path,
                             completed_at=datetime.utcnow())
        except Exception as e:
            log.exception("Job %s 失败", job_id)
            self._update_job(job_id, status="failed", error=str(e)[:500],
                             completed_at=datetime.utcnow())

    def _update_job(self, job_id: int, **fields) -> None:
        """sync session 更新 Job 行（线程内直接写，WAL 允许并发）"""
        factory = get_sync_session_factory()
        try:
            with factory() as session:
                job = session.get(Job, job_id)
                if job is None:
                    return
                for k, v in fields.items():
                    setattr(job, k, v)
                session.commit()
        except Exception:
            log.warning("Job %s 更新失败: %s", job_id, list(fields.keys()), exc_info=True)


_runner: JobRunner | None = None


def get_job_runner() -> JobRunner:
    global _runner
    if _runner is None:
        _runner = JobRunner()
    return _runner


async def start_job_for_project(session, project_id: str, user: User) -> Job:
    """共享助手：校验 ownership + 注册 providers + 建 Job 行 + 入线程池。
    被 POST /api/projects/{id}/run 和 POST /api/jobs 复用。
    """
    result = await session.execute(select(Project).where(Project.project_id == project_id))
    project = result.scalar_one_or_none()
    if project is None or project.user_id != user.id:
        from fastapi import HTTPException
        raise HTTPException(404, "项目不存在或无权访问")

    await auto_register_all(session)  # env 优先 + DB key 池

    job = Job(project_id=project.id, user_id=user.id, status="queued")
    session.add(job)
    await session.commit()
    await session.refresh(job)

    get_job_runner().start_job(job.id, project.project_id)
    return job
