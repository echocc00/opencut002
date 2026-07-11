"""OpenCut v3.0 FastAPI 应用入口"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .panel_routes import router as panel_router
from .project_routes import router as project_router

app = FastAPI(title="OpenCut v3.0", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(panel_router)
app.include_router(project_router)


@app.get("/")
async def root():
    return {"name": "OpenCut v3.0", "version": "3.0.0", "status": "running"}
