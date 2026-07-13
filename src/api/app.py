"""OpenCut v3.0 FastAPI 应用入口"""
from __future__ import annotations

import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .panel_routes import router as panel_router
from .project_routes import router as project_router

load_dotenv()

app = FastAPI(title="OpenCut v3.0", version="0.4.0")

# CORS：生产环境用 OPENCUT_CORS_ORIGINS 设置白名单（逗号分隔）；未设置时默认放开（仅开发用）
_cors_env = os.environ.get("OPENCUT_CORS_ORIGINS", "").split(",")
allow_origins = [o.strip() for o in _cors_env if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(panel_router)
app.include_router(project_router)


@app.get("/")
async def root():
    return {"name": "OpenCut v3.0", "version": "0.4.0", "status": "running"}
