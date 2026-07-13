"""测试公共 fixture：临时 DB + 带/不带 auth 的 AsyncClient"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


def _reset_singletons():
    """重置 settings + db engine 单例，使新 env（OPENCUT_DATABASE_URL）生效"""
    import src.config as config_mod
    config_mod._settings = None
    from src.db.engine import reset_engine_for_tests
    reset_engine_for_tests()


@pytest.fixture
def fresh_db(monkeypatch, tmp_path):
    """每个测试用独立临时 SQLite 文件库"""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("OPENCUT_DATABASE_URL", f"sqlite+aiosqlite:///{db_file.as_posix()}")
    _reset_singletons()
    yield db_file
    _reset_singletons()


@pytest_asyncio.fixture
async def async_client(fresh_db):
    """无认证的 AsyncClient（直连 FastAPI app）"""
    from src.api.app import app
    from src.db.engine import init_db
    await init_db()  # ASGITransport 不跑 lifespan，手动建表
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def auth_client(async_client):
    """注册测试用户并带 Authorization 头"""
    resp = await async_client.post("/api/auth/register", json={
        "email": "test@example.com", "username": "testuser", "password": "pass1234",
    })
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    async_client.headers["Authorization"] = f"Bearer {token}"
    yield async_client
