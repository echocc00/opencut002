"""Health 端点测试（v0.6.1）- 锁定无路径泄漏 + 端点行为。"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCUT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("OPENCUT_DOMAINS_DIR", str(tmp_path / "domains"))
    # settings 单例缓存了首次的 env，必须重置才让 monkeypatch 生效
    from src import config
    config._settings = None
    config.clear_domain_cache()
    yield
    config._settings = None
    config.clear_domain_cache()


class TestCheckFfmpeg:
    def test_ffmpeg_not_found(self):
        with patch("src.api.health.shutil.which", return_value=None):
            from src.api.health import _check_ffmpeg
            r = _check_ffmpeg()
        assert r["ok"] is False

    def test_ffmpeg_found(self):
        from src.api.health import _check_ffmpeg
        r = _check_ffmpeg()
        # CI/本地有 ffmpeg 应 ok（无 ffmpeg 则 ok=False，都接受，只校验结构）
        assert "ok" in r
        if r["ok"]:
            assert "version" in r
        # 不泄漏绝对路径
        assert "path" not in r


class TestCheckDataDir:
    def test_writable_data_dir(self, tmp_path):
        from src.api.health import _check_data_dir
        r = _check_data_dir()
        assert r["ok"] is True
        assert r["writable"] is True
        # 修：不返回绝对路径（防侦察）
        assert "path" not in r

    def test_nonexistent_data_dir_no_mkdir_side_effect(self, tmp_path, monkeypatch):
        """修：health 检查不创建目录（去副作用）。"""
        new_dir = tmp_path / "nonexistent"
        monkeypatch.setenv("OPENCUT_DATA_DIR", str(new_dir))
        from src.api.health import _check_data_dir
        r = _check_data_dir()
        assert r["ok"] is False
        assert not new_dir.exists()  # 没被创建

    def test_unwritable_data_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENCUT_DATA_DIR", str(tmp_path))
        from src.api.health import _check_data_dir
        # 让 tempfile 失败
        with patch("src.api.health.tempfile.NamedTemporaryFile", side_effect=OSError("denied")):
            r = _check_data_dir()
        assert r["ok"] is False
        assert "error" in r


class TestCheckDomainsDir:
    def test_empty_domains_dir(self, tmp_path, monkeypatch):
        # tmp_path/domains 不存在 -> ok=False
        from src.api.health import _check_domains_dir
        r = _check_domains_dir()
        assert r["ok"] is False
        assert r["domain_count"] == 0
        assert "path" not in r  # 不泄漏路径

    def test_with_domain(self, tmp_path, monkeypatch):
        (tmp_path / "domains" / "education").mkdir(parents=True)
        from src.api.health import _check_domains_dir
        r = _check_domains_dir()
        assert r["ok"] is True
        assert r["domain_count"] >= 1


class TestVersion:
    def test_version_from_init(self):
        from src.api.health import _version
        from src import __version__
        assert _version() == __version__


class TestHealthEndpoints:
    """端点集成（patch init_db 避免 DB 依赖）。"""

    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENCUT_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/t.db")
        from src.api import app as app_mod
        from fastapi.testclient import TestClient
        # saas 有 lifespan/init_db -> patch 掉避免 DB 依赖；main 无 lifespan -> 直接用
        if hasattr(app_mod, "init_db"):
            async def _noop():
                pass
            with patch("src.api.app.init_db", _noop):
                with TestClient(app_mod.app) as c:
                    yield c
        else:
            with TestClient(app_mod.app) as c:
                yield c

    def test_liveness(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["service"] == "opencut-v3"

    def test_detail_no_path_leak(self, client):
        """修 CRITICAL：/health/detail 不泄漏绝对路径。"""
        r = client.get("/health/detail")
        assert r.status_code == 200
        body = str(r.json())
        # 不含常见绝对路径前缀
        for prefix in [str(Path.home()), "/home/", "C:\\\\", "F:\\\\"]:
            assert prefix not in body, f"路径泄漏: {prefix} in {body}"

    def test_ready_returns_200_or_503(self, client):
        r = client.get("/health/ready")
        assert r.status_code in (200, 503)
        body = r.json()
        assert "checks" in body
