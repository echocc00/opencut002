"""Admin 路由：API Key 池管理（C0.8 平台托管）。

管理员把 LLM provider key 录到 DB，用户不接触 .env。auto_register_all 读 DB 补齐。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.engine import get_session
from ..db.models import ApiKey, User
from .auth import get_admin_user

router = APIRouter(prefix="/api/admin/keys", tags=["admin"])


class KeyCreate(BaseModel):
    provider: str  # minimax/deepseek/doubao/qwen
    api_key: str
    api_base: str | None = None
    model: str | None = None
    is_active: bool = True


class KeyOut(BaseModel):
    id: int
    provider: str
    api_key: str  # 列表返回完整 key（仅管理员可见）
    api_base: str | None
    model: str | None
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("", response_model=list[KeyOut])
async def list_keys(
    _admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(ApiKey).order_by(ApiKey.provider))
    return result.scalars().all()


@router.post("", response_model=KeyOut, status_code=201)
async def add_key(
    payload: KeyCreate,
    _admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    key = ApiKey(
        provider=payload.provider,
        api_key=payload.api_key,
        api_base=payload.api_base,
        model=payload.model,
        is_active=payload.is_active,
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)
    return key
