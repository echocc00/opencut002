"""异步 + 同步 SQLAlchemy 引擎 + 会话工厂。

MVP 用 SQLite。API 用 async engine（aiosqlite）；job runner 线程用 sync engine（sqlite3）。
两个 engine 指向同一文件，开启 WAL 模式允许并发「async 读 + sync 写」。
切 Postgres 时改 OPENCUT_DATABASE_URL（async URL）即可，sync URL 自动推导。
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ..config import get_settings


class Base(DeclarativeBase):
    pass


def _set_wal(dbapi_conn, _):
    """SQLite WAL：允许并发读写（job 线程写 + API 异步读）"""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_sync_engine = None
_sync_session_factory: sessionmaker | None = None


def _ensure_sqlite_dir(database_url: str) -> None:
    if database_url.startswith("sqlite"):
        db_path = database_url.split("///")[-1]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def get_engine():
    global _engine
    if _engine is None:
        s = get_settings()
        _ensure_sqlite_dir(s.database_url)
        _engine = create_async_engine(s.database_url, echo=False)
        event.listen(_engine.sync_engine, "connect", _set_wal)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)
    return _session_factory


async def get_session() -> AsyncSession:
    """FastAPI 依赖：每请求一个异步会话"""
    factory = get_session_factory()
    async with factory() as session:
        yield session


def get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        s = get_settings()
        # aiosqlite URL -> 同步 sqlite URL
        sync_url = s.database_url.replace("sqlite+aiosqlite", "sqlite")
        _ensure_sqlite_dir(sync_url)
        _sync_engine = create_engine(sync_url, echo=False)
        event.listen(_sync_engine, "connect", _set_wal)
    return _sync_engine


def get_sync_session_factory() -> sessionmaker:
    global _sync_session_factory
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(get_sync_engine(), expire_on_commit=False)
    return _sync_session_factory


async def init_db() -> None:
    """建表（Base.metadata.create_all，不上 alembic）"""
    from . import models  # noqa: F401
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def reset_engine_for_tests() -> None:
    """测试用：重置单例引擎（切到测试库后强制重建）"""
    global _engine, _session_factory, _sync_engine, _sync_session_factory
    _engine = None
    _session_factory = None
    _sync_engine = None
    _sync_session_factory = None
