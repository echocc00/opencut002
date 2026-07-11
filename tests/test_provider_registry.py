"""Provider 注册表单元测试 - 验证 R02 多 endpoint 注册、占位符过滤、list_providers"""
import os
import pytest
from src.providers.provider_registry import (
    Provider, ProviderResponse, register_provider, get_provider, clear_registry,
    list_providers, _is_real_key, auto_register_from_env,
)


def setup_function():
    clear_registry()


def test_is_real_key_filters_placeholders():
    assert _is_real_key("sk-realkey123") is True
    assert _is_real_key("") is False
    assert _is_real_key("your_deepseek_key") is False
    assert _is_real_key("sk-xxx-placeholder") is False
    assert _is_real_key("  your_minimax  ") is False


def test_register_and_get_provider():
    p = Provider("test")
    register_provider("test", p)
    assert "test" in list_providers()
    assert get_provider("test") is p


def test_get_provider_missing_raises():
    with pytest.raises(KeyError):
        get_provider("nonexistent")


def test_list_providers_returns_registered_names():
    register_provider("a", Provider("a"))
    register_provider("b", Provider("b"))
    assert set(list_providers()) == {"a", "b"}


def test_auto_register_skips_placeholder_keys(monkeypatch):
    """占位符 key 不应注册成 provider"""
    monkeypatch.setenv("MINIMAX_API_KEY", "your_minimax_key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_key")
    monkeypatch.delenv("DOUBAO_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    registered = auto_register_from_env()
    assert registered == []
    assert list_providers() == []


def test_auto_register_real_key(monkeypatch):
    """真实 key 注册对应 provider"""
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-realminimax123")
    monkeypatch.setenv("MINIMAX_API_BASE", "https://api.minimaxi.com/anthropic")
    monkeypatch.setenv("MINIMAX_MODEL", "MiniMax M3")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DOUBAO_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    registered = auto_register_from_env()
    assert registered == ["minimax"]
    assert "minimax" in list_providers()


@pytest.mark.asyncio
async def test_provider_complete_wraps_str_to_response():
    """complete_fn 返回 str 时，Provider 包装成 ProviderResponse"""
    async def mock_complete(prompt, **kw):
        return "raw response text"
    p = Provider("mock", mock_complete)
    resp = await p.complete("hello")
    assert isinstance(resp, ProviderResponse)
    assert resp.text == "raw response text"
    assert resp.model == "mock"
    assert resp.input_tokens == 0  # str mock 无 usage


@pytest.mark.asyncio
async def test_provider_complete_passes_through_provider_response():
    """complete_fn 返回 ProviderResponse 时直接透传（含 usage）"""
    async def mock_complete(prompt, **kw):
        return ProviderResponse(text="hi", input_tokens=10, output_tokens=5, model="test-model")
    p = Provider("mock", mock_complete)
    resp = await p.complete("hello")
    assert resp.text == "hi"
    assert resp.input_tokens == 10
    assert resp.output_tokens == 5
    assert resp.model == "test-model"
