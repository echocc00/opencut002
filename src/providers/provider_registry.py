"""Provider 注册表 - 支持 MiniMax (Anthropic兼容) 和 OpenAI 格式"""
from __future__ import annotations

from typing import Any
import httpx


class Provider:
    def __init__(self, name: str, complete_fn=None):
        self.name = name
        self._complete_fn = complete_fn

    async def complete(self, prompt: str, **kwargs: Any) -> str:
        if self._complete_fn:
            return await self._complete_fn(prompt, **kwargs)
        raise NotImplementedError(f"Provider {self.name} has no complete function")


def make_minimax_provider(api_key: str, api_base: str = "https://api.minimaxi.com/anthropic",
                          model: str = "MiniMax M3"):
    """创建 MiniMax Provider (Anthropic兼容API)"""
    async def complete_fn(prompt: str, **kw) -> str:
        max_tokens = kw.get("max_tokens", 8192)
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{api_base}/v1/messages",
                headers={"Content-Type": "application/json", "x-api-key": api_key},
                json={"model": model, "max_tokens": max_tokens,
                      "messages": [{"role": "user", "content": prompt}]},
            )
        if resp.status_code != 200:
            raise RuntimeError(f"MiniMax API错误 {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return data["content"][0]["text"]

    return Provider("minimax", complete_fn)


def make_openai_provider(name: str, api_base: str, api_key: str, model: str):
    """创建 OpenAI 兼容的 Provider"""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(base_url=api_base, api_key=api_key)

    async def complete_fn(prompt: str, **kw) -> str:
        max_tokens = kw.get("max_tokens", 4096)
        resp = await client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}], max_tokens=max_tokens,
        )
        return resp.choices[0].message.content

    return Provider(name, complete_fn)


_registry: dict[str, Provider] = {}

def register_provider(name: str, provider: Provider):
    _registry[name] = provider

def get_provider(name: str) -> Provider:
    if name not in _registry:
        raise KeyError(f"Provider '{name}' not registered. Available: {list(_registry.keys())}")
    return _registry[name]

def clear_registry():
    _registry.clear()

def auto_register_from_env():
    """从环境变量自动注册 Provider"""
    import os
    key = os.environ.get("MINIMAX_API_KEY", "")
    if not key:
        # 尝试从文件读取
        try:
            with open("../minimax-key.txt") as f:
                lines = f.read().strip().split("\n")
                key = lines[0].strip()
                api_base = lines[2].strip() if len(lines) > 2 else "https://api.minimaxi.com/anthropic"
                model = lines[4].strip() if len(lines) > 4 else "MiniMax M3"
        except:
            return False
    else:
        api_base = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com/anthropic")
        model = os.environ.get("MINIMAX_MODEL", "MiniMax M3")

    provider = make_minimax_provider(key, api_base, model)
    register_provider("minimax", provider)
    register_provider("deepseek", provider)
    register_provider("doubao", provider)
    register_provider("qwen", provider)
    return True
