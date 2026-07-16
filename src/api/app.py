"""OpenCut v3.0 FastAPI 应用入口"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..db.engine import init_db
from .. import __version__
from .admin_routes import router as admin_router
from .auth_routes import router as auth_router
from .health import router as health_router
from .job_routes import router as job_router
from .panel_routes import router as panel_router
from .project_routes import router as project_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时建表（create_all，不上 alembic）
    await init_db()
    yield


app = FastAPI(title="OpenCut v3.0", version=__version__, lifespan=lifespan)

# CORS：生产环境用 OPENCUT_CORS_ORIGINS 设置白名单（逗号分隔）；未设置时默认放开（仅开发用）
_cors_env = os.environ.get("OPENCUT_CORS_ORIGINS", "").split(",")
allow_origins = [o.strip() for o in _cors_env if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(job_router)
app.include_router(panel_router)
app.include_router(project_router)


@app.get("/")
async def root():
    return {"name": "OpenCut v3.0", "version": __version__, "status": "running"}
