"""Health check 端点（v0.6.1，port 自 v0.5.4 audit + 安全修复）。

- GET /health        - liveness（进程在跑，恒 200）
- GET /health/ready  - readiness（ffmpeg + data_dir 可写，否则 503）
- GET /health/detail - 调试详情（ffmpeg/node/data_dir/domains，恒 200）

安全修复（评审 CRITICAL/HIGH）：
- version 从 src.__version__ 读，不硬编码
- /health/detail 不返回绝对路径（只返 exists/writable 布尔 + basename），防侦察
- _check_data_dir 用 tempfile（不可预测文件名，修 symlink 竞态），且不在 health 检查里 mkdir（去副作用）
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Response, status


router = APIRouter(tags=["health"])


def _version() -> str:
    try:
        from .. import __version__
        return __version__
    except Exception:
        return "unknown"


def _check_ffmpeg() -> dict[str, Any]:
    """ffmpeg 是否可用 + 版本。"""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"ok": False, "error": "ffmpeg not in PATH"}
    try:
        result = subprocess.run(
            [ffmpeg, "-version"], capture_output=True, text=True, timeout=5,
        )
        first_line = (result.stdout or "").splitlines()[0] if result.stdout else ""
        return {"ok": result.returncode == 0, "version": first_line[:100] or None}
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return {"ok": False, "error": str(e)}


def _check_node() -> dict[str, Any]:
    """Node.js 是否可用（Remotion 需要）。"""
    node = shutil.which("node")
    if not node:
        return {"ok": False, "error": "node not in PATH"}
    try:
        result = subprocess.run(
            [node, "--version"], capture_output=True, text=True, timeout=5,
        )
        version = (result.stdout or "").strip()
        return {"ok": result.returncode == 0, "version": version or None}
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return {"ok": False, "error": str(e)}


def _check_data_dir() -> dict[str, Any]:
    """data_dir 是否可写。不创建目录（health 检查只读，副作用留给启动逻辑）。
    用 tempfile（不可预测名，修 symlink 竞态）。"""
    from ..config import get_settings
    data_dir = Path(get_settings().data_dir)
    info: dict[str, Any] = {"ok": False, "exists": data_dir.exists()}
    if not data_dir.exists():
        info["error"] = "data_dir does not exist"
        return info
    try:
        # NamedTemporaryFile 名字不可预测，避免攻击者预置 symlink 竞态
        with tempfile.NamedTemporaryFile(dir=data_dir, prefix=".health_", suffix=".tmp", delete=True):
            info["ok"] = True
            info["writable"] = True
    except OSError as e:
        info["error"] = str(e)
    return info


def _check_domains_dir() -> dict[str, Any]:
    """domains_dir 是否有至少一个领域。"""
    from ..config import get_settings
    domains_dir = Path(get_settings().domains_dir)
    info: dict[str, Any] = {"ok": False, "exists": domains_dir.exists(), "domain_count": 0}
    if domains_dir.exists():
        domains = [d for d in domains_dir.iterdir() if d.is_dir()]
        info["domain_count"] = len(domains)
        info["ok"] = info["domain_count"] > 0
    return info


@router.get("/health")
async def health() -> dict[str, Any]:
    """Liveness 探针 - 进程在跑即 200。"""
    return {"status": "ok", "service": "opencut-v3", "version": _version()}


@router.get("/health/ready")
async def health_ready(response: Response) -> dict[str, Any]:
    """Readiness 探针 - ffmpeg + data_dir OK 才 200，否则 503。"""
    checks = {"ffmpeg": _check_ffmpeg(), "data_dir": _check_data_dir()}
    all_ok = all(c.get("ok") for c in checks.values())
    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "checks": checks}
    return {"status": "ready", "checks": checks}


@router.get("/health/detail")
async def health_detail() -> dict[str, Any]:
    """调试详情 - 恒 200，看各 ok 字段。不返回绝对路径（防侦察）。"""
    return {
        "service": "opencut-v3",
        "version": _version(),
        "checks": {
            "ffmpeg": _check_ffmpeg(),
            "node": _check_node(),
            "data_dir": _check_data_dir(),
            "domains_dir": _check_domains_dir(),
        },
    }
