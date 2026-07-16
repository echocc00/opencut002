"""per-tool fallback 测试（v0.6.2）- call_tool_with_fallback。"""
from __future__ import annotations

import pytest

from src.providers.fallback import call_tool_with_fallback


class FakeStatusError(Exception):
    def __init__(self, code: int):
        super().__init__(f"HTTP {code}")
        self.status_code = code


def _async_fn(name: str, result=None, exc=None):
    async def fn(**kwargs):
        if exc is not None:
            raise exc
        return result if result is not None else name
    fn.__name__ = name
    return fn


class TestCallToolWithFallback:
    @pytest.mark.asyncio
    async def test_primary_succeeds(self):
        primary = _async_fn("primary", result="ok")
        fallback = _async_fn("fallback", result="should_not_run")
        r = await call_tool_with_fallback(primary, [fallback], x=1)
        assert r == "ok"

    @pytest.mark.asyncio
    async def test_transient_falls_through(self):
        primary = _async_fn("primary", exc=FakeStatusError(500))
        fallback = _async_fn("fallback", result="recovered")
        r = await call_tool_with_fallback(primary, [fallback])
        assert r == "recovered"

    @pytest.mark.asyncio
    async def test_permanent_raises_immediately(self):
        """永久错误（4xx/auth）不 fallback，直 raise。"""
        primary = _async_fn("primary", exc=FakeStatusError(401))
        fallback = _async_fn("fallback", result="should_not_run")
        with pytest.raises(FakeStatusError):
            await call_tool_with_fallback(primary, [fallback])

    @pytest.mark.asyncio
    async def test_value_error_permanent(self):
        primary = _async_fn("primary", exc=ValueError("bad arg"))
        fallback = _async_fn("fallback", result="x")
        with pytest.raises(ValueError):
            await call_tool_with_fallback(primary, [fallback])

    @pytest.mark.asyncio
    async def test_all_fail_raises_runtime(self):
        primary = _async_fn("primary", exc=FakeStatusError(500))
        fb1 = _async_fn("fb1", exc=FakeStatusError(500))
        fb2 = _async_fn("fb2", exc=FakeStatusError(503))
        with pytest.raises(RuntimeError, match="全部 3 个 tool 失败"):
            await call_tool_with_fallback(primary, [fb1, fb2])

    @pytest.mark.asyncio
    async def test_empty_fallback_list_transient_raises_runtime(self):
        """空 fallback 列表 + 主瞬时错误 -> RuntimeError（无降级可用）。"""
        primary = _async_fn("primary", exc=FakeStatusError(500))
        with pytest.raises(RuntimeError, match="全部 1 个 tool 失败"):
            await call_tool_with_fallback(primary, [])

    @pytest.mark.asyncio
    async def test_empty_fallback_list_primary_ok(self):
        """空 fallback 列表 + 主成功 -> 正常返回。"""
        primary = _async_fn("primary", result="ok")
        r = await call_tool_with_fallback(primary, [], a=1, b=2)
        assert r == "ok"

    @pytest.mark.asyncio
    async def test_chains_multiple_fallbacks(self):
        primary = _async_fn("primary", exc=FakeStatusError(500))
        fb1 = _async_fn("fb1", exc=FakeStatusError(500))
        fb2 = _async_fn("fb2", result="third_time_charm")
        r = await call_tool_with_fallback(primary, [fb1, fb2])
        assert r == "third_time_charm"
