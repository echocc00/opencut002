"""C0.8 API Key 平台托管测试：DB key 池 + auto_register_all + admin CRUD"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from src.db.engine import get_session_factory
from src.db.models import ApiKey, User
from src.providers.provider_registry import auto_register_all, clear_registry, list_providers


async def _add_user(async_client, email, username, is_admin=False):
    """注册用户，可选提为 admin（直接改 DB）"""
    resp = await async_client.post("/api/auth/register", json={
        "email": email, "username": username, "password": "pass1234",
    })
    assert resp.status_code == 201
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.is_admin = is_admin
        await session.commit()
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_db_key_fills_gap(async_client, fresh_db, monkeypatch):
    """env 无 key 时，DB key 池补齐注册"""
    clear_registry()
    # 模拟 env 无任何真实 key
    monkeypatch.setattr(
        "src.providers.provider_registry.auto_register_from_env", lambda: []
    )
    factory = get_session_factory()
    async with factory() as session:
        session.add(ApiKey(provider="minimax", api_key="db-minimax-key"))
        await session.commit()
        registered = await auto_register_all(session)
    assert "minimax" in registered
    assert "minimax" in list_providers()
    clear_registry()


@pytest.mark.asyncio
async def test_env_takes_precedence_over_db(async_client, fresh_db, monkeypatch):
    """env 已注册的 provider，DB 不覆盖"""
    clear_registry()
    # env 注册 minimax
    monkeypatch.setattr(
        "src.providers.provider_registry.auto_register_from_env",
        lambda: ["minimax"],
    )
    from src.providers.provider_registry import make_minimax_provider, register_provider
    register_provider("minimax", make_minimax_provider("env-key"))
    factory = get_session_factory()
    async with factory() as session:
        session.add(ApiKey(provider="minimax", api_key="db-key-should-not-override"))
        await session.commit()
        await auto_register_all(session)
    # env 的 provider 仍在，DB 没重复注册
    assert list_providers().count("minimax") == 1
    clear_registry()


@pytest.mark.asyncio
async def test_inactive_db_key_skipped(async_client, fresh_db, monkeypatch):
    """is_active=False 的 DB key 不注册"""
    clear_registry()
    monkeypatch.setattr(
        "src.providers.provider_registry.auto_register_from_env", lambda: []
    )
    factory = get_session_factory()
    async with factory() as session:
        session.add(ApiKey(provider="minimax", api_key="inactive-key", is_active=False))
        await session.commit()
        registered = await auto_register_all(session)
    assert "minimax" not in registered
    clear_registry()


@pytest.mark.asyncio
async def test_openai_compatible_db_key_registered(async_client, fresh_db, monkeypatch):
    """doubao（OpenAI 兼容）DB key 能注册"""
    clear_registry()
    monkeypatch.setattr(
        "src.providers.provider_registry.auto_register_from_env", lambda: []
    )
    factory = get_session_factory()
    async with factory() as session:
        session.add(ApiKey(provider="doubao", api_key="db-doubao-key",
                           api_base="https://ark.example.com/api/v3", model="doubao-test"))
        await session.commit()
        registered = await auto_register_all(session)
    assert "doubao" in registered
    clear_registry()


@pytest.mark.asyncio
async def test_admin_can_list_and_add_keys(async_client, fresh_db):
    """admin 用户能 GET/POST /api/admin/keys"""
    admin_token = await _add_user(async_client, "admin@example.com", "adminuser", is_admin=True)
    async_client.headers["Authorization"] = f"Bearer {admin_token}"

    # 先空列表
    resp = await async_client.get("/api/admin/keys")
    assert resp.status_code == 200
    assert resp.json() == []

    # 加一个 key
    resp = await async_client.post("/api/admin/keys", json={
        "provider": "minimax", "api_key": "admin-added-key", "model": "MiniMax M3",
    })
    assert resp.status_code == 201
    created = resp.json()
    assert created["provider"] == "minimax"
    assert created["api_key"] == "admin-added-key"
    assert created["is_active"] is True

    # 再列表
    resp = await async_client.get("/api/admin/keys")
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_non_admin_cannot_access_admin_keys(auth_client):
    """普通用户访问 admin 端点 -> 403"""
    resp = await auth_client.get("/api/admin/keys")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_admin_keys_401(async_client):
    """未登录访问 admin 端点 -> 401"""
    resp = await async_client.get("/api/admin/keys")
    assert resp.status_code == 401
