"""C0.5 用户系统测试：注册/登录/JWT/鉴权"""
from __future__ import annotations

import jwt
import pytest

from src.config import get_settings


@pytest.mark.asyncio
async def test_register_creates_user_with_hashed_password(async_client):
    resp = await async_client.post("/api/auth/register", json={
        "email": "a@example.com", "username": "alice", "password": "secret123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"]["email"] == "a@example.com"
    assert data["user"]["username"] == "alice"
    assert data["user"]["is_admin"] is False


@pytest.mark.asyncio
async def test_register_duplicate_email_409(async_client):
    payload = {"email": "dup@example.com", "username": "u1", "password": "secret123"}
    await async_client.post("/api/auth/register", json=payload)
    payload["username"] = "u2"  # 换用户名，同邮箱
    resp = await async_client.post("/api/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_duplicate_username_409(async_client):
    await async_client.post("/api/auth/register", json={
        "email": "e1@example.com", "username": "sameuser", "password": "secret123",
    })
    resp = await async_client.post("/api/auth/register", json={
        "email": "e2@example.com", "username": "sameuser", "password": "secret123",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_success_returns_token(async_client):
    await async_client.post("/api/auth/register", json={
        "email": "login@example.com", "username": "loginuser", "password": "secret123",
    })
    resp = await async_client.post("/api/auth/login", json={
        "email": "login@example.com", "password": "secret123",
    })
    assert resp.status_code == 200
    assert resp.json()["access_token"]


@pytest.mark.asyncio
async def test_login_wrong_password_401(async_client):
    await async_client.post("/api/auth/register", json={
        "email": "wp@example.com", "username": "wpuser", "password": "secret123",
    })
    resp = await async_client.post("/api/auth/login", json={
        "email": "wp@example.com", "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email_401(async_client):
    resp = await async_client.post("/api/auth/login", json={
        "email": "nobody@example.com", "password": "secret123",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_without_token_401(async_client):
    resp = await async_client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_token(auth_client):
    resp = await auth_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_me_with_invalid_token_401(async_client):
    async_client.headers["Authorization"] = "Bearer not.a.real.token"
    resp = await async_client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_jwt_contains_user_id_and_exp(async_client):
    resp = await async_client.post("/api/auth/register", json={
        "email": "jwt@example.com", "username": "jwtuser", "password": "secret123",
    })
    token = resp.json()["access_token"]
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[get_settings().jwt_algorithm])
    assert payload["email"] == "jwt@example.com"
    assert "exp" in payload
    assert "sub" in payload


@pytest.mark.asyncio
async def test_password_is_hashed_not_plaintext(async_client, fresh_db):
    """注册后 DB 里存的是哈希，不是明文"""
    from src.db.engine import get_session_factory
    from src.db.models import User
    from sqlalchemy import select
    await async_client.post("/api/auth/register", json={
        "email": "hash@example.com", "username": "hashuser", "password": "plaintext123",
    })
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(User).where(User.email == "hash@example.com"))
        user = result.scalar_one()
    assert user.password_hash != "plaintext123"
    assert "$" in user.password_hash or len(user.password_hash) > 30  # bcrypt hash 形态
