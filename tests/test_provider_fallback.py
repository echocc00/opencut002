"""Provider fallback 测试（v0.6.1）- 锁定 auth 分类修复（防 401/403 误转移泄漏 prompt）。"""
from __future__ import annotations

import pytest

from src.providers.provider_registry import (
    Provider, ProviderResponse, register_provider, clear_registry,
)
from src.providers.fallback import _is_transient_error, call_with_fallback


class FakeStatusError(Exception):
    """带 status_code 的模拟 HTTP 错误。"""
    def __init__(self, code: int):
        super().__init__(f"HTTP {code}")
        self.status_code = code


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


def _make_provider(name: str, complete_fn):
    register_provider(name, Provider(name, complete_fn))


class TestIsTransientError:
    def test_500_transient(self):
        assert _is_transient_error(FakeStatusError(500)) is True

    def test_429_transient(self):
        assert _is_transient_error(FakeStatusError(429)) is True

    def test_408_transient(self):
        assert _is_transient_error(FakeStatusError(408)) is True

    def test_401_permanent(self):
        """修：401 auth 不转移，防 prompt 泄漏到下一个 provider。"""
        assert _is_transient_error(FakeStatusError(401)) is False

    def test_403_permanent(self):
        assert _is_transient_error(FakeStatusError(403)) is False

    def test_400_permanent(self):
        assert _is_transient_error(FakeStatusError(400)) is False

    def test_value_error_permanent(self):
        assert _is_transient_error(ValueError("bad")) is False

    def test_generic_runtime_transient(self):
        assert _is_transient_error(RuntimeError("network blip")) is True

    def test_minimax_401_message_permanent(self):
        """minimax 通用 RuntimeError('API错误 401') 按消息启发式判永久。"""
        assert _is_transient_error(RuntimeError("MiniMax API错误 401: unauthorized")) is False
        assert _is_transient_error(RuntimeError("MiniMax API错误 403: forbidden")) is False


class TestCallWithFallback:
    @pytest.mark.asyncio
    async def test_first_provider_succeeds(self):
        async def ok(prompt, **kw):
            return ProviderResponse(text="result", model="a")
        _make_provider("a", ok)
        r = await call_with_fallback("p", ["a"])
        assert r.text == "result"

    @pytest.mark.asyncio
    async def test_transient_error_falls_back(self):
        async def fail(prompt, **kw):
            raise FakeStatusError(500)
        async def ok(prompt, **kw):
            return ProviderResponse(text="b-result", model="b")
        _make_provider("a", fail)
        _make_provider("b", ok)
        r = await call_with_fallback("p", ["a", "b"], retry_delay=0)
        assert r.text == "b-result"

    @pytest.mark.asyncio
    async def test_permanent_auth_error_does_not_fallback(self):
        """修：401 不转移 -> 不调 b，直接 raise（防 prompt 发给 b）。"""
        calls = []
        async def fail_401(prompt, **kw):
            calls.append(("a", prompt))
            raise FakeStatusError(401)
        async def ok(prompt, **kw):
            calls.append(("b", prompt))
            return ProviderResponse(text="b", model="b")
        _make_provider("a", fail_401)
        _make_provider("b", ok)
        with pytest.raises(Exception):
            await call_with_fallback("secret-prompt", ["a", "b"], retry_delay=0)
        # b 没被调用 -> prompt 没泄漏
        assert not any(c[0] == "b" for c in calls)

    @pytest.mark.asyncio
    async def test_empty_response_falls_back(self):
        async def empty(prompt, **kw):
            return ProviderResponse(text="", model="a")
        async def ok(prompt, **kw):
            return ProviderResponse(text="real", model="b")
        _make_provider("a", empty)
        _make_provider("b", ok)
        r = await call_with_fallback("p", ["a", "b"], retry_delay=0)
        assert r.text == "real"

    @pytest.mark.asyncio
    async def test_all_fail_raises(self):
        async def fail(prompt, **kw):
            raise FakeStatusError(500)
        _make_provider("a", fail)
        _make_provider("b", fail)
        with pytest.raises(RuntimeError, match="失败"):
            await call_with_fallback("p", ["a", "b"], retry_delay=0)

    @pytest.mark.asyncio
    async def test_empty_providers_raises(self):
        with pytest.raises(ValueError):
            await call_with_fallback("p", [])
