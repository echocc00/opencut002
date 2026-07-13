"""Provider 注册表 - 支持 MiniMax (Anthropic兼容) 和 OpenAI 格式"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import httpx


@dataclass
class ProviderResponse:
    """Provider 调用结果（含 token 用量用于成本追踪）"""
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


class Provider:
    def __init__(self, name: str, complete_fn=None):
        self.name = name
        self._complete_fn = complete_fn

    async def complete(self, prompt: str, **kwargs: Any) -> ProviderResponse:
        if self._complete_fn:
            result = await self._complete_fn(prompt, **kwargs)
            if isinstance(result, ProviderResponse):
                return result
            # complete_fn 返回 str（如测试 mock）-> 包装，无 usage
            return ProviderResponse(text=str(result), model=self.name)
        raise NotImplementedError(f"Provider {self.name} has no complete function")


def _guess_media_type(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/jpeg")


def make_minimax_provider(api_key: str, api_base: str = "https://api.minimaxi.com/anthropic",
                          model: str = "MiniMax M3"):
    """创建 MiniMax Provider (Anthropic兼容API，M3 支持多模态 image block)"""
    async def complete_fn(prompt: str, **kw) -> str:
        import base64
        max_tokens = kw.get("max_tokens", 8192)
        images = kw.get("images")  # 多模态：图片路径列表
        if images:
            content: list = [{"type": "text", "text": prompt}]
            for img_path in images:
                try:
                    with open(img_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    content.append({"type": "image", "source": {
                        "type": "base64",
                        "media_type": _guess_media_type(img_path),
                        "data": b64,
                    }})
                except Exception:
                    pass  # 跳过无法读取的图片
            messages = [{"role": "user", "content": content}]
        else:
            messages = [{"role": "user", "content": prompt}]
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{api_base}/v1/messages",
                headers={"Content-Type": "application/json", "x-api-key": api_key},
                json={"model": model, "max_tokens": max_tokens, "messages": messages},
            )
        if resp.status_code != 200:
            raise RuntimeError(f"MiniMax API错误 {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        usage = data.get("usage", {})
        return ProviderResponse(
            text=data["content"][0]["text"],
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            model=model,
        )

    return Provider("minimax", complete_fn)


def make_openai_provider(name: str, api_base: str, api_key: str, model: str):
    """创建 OpenAI 兼容的 Provider"""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(base_url=api_base, api_key=api_key)

    async def complete_fn(prompt: str, **kw) -> str:
        import base64
        max_tokens = kw.get("max_tokens", 4096)
        images = kw.get("images")  # 多模态：图片路径列表
        content: list = [{"type": "text", "text": prompt}]
        if images:
            for img_path in images:
                try:
                    with open(img_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
                except Exception:
                    pass  # 跳过无法读取的图片
        resp = await client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": content}], max_tokens=max_tokens,
        )
        usage = resp.usage
        return ProviderResponse(
            text=resp.choices[0].message.content,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=model,
        )

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

def _is_real_key(key: str) -> bool:
    """过滤占位符 key（空 / your_xxx / sk-xxx / 含 placeholder）"""
    if not key:
        return False
    k = key.strip().lower()
    return not (k.startswith("your_") or k.startswith("sk-xxx") or "placeholder" in k)


def auto_register_from_env() -> list[str]:
    """从环境变量自动注册 Provider，返回已注册名列表。

    每个 provider 独立实例（不再 4 名指同一对象）。占位符 key 跳过注册。
    至少配置一个真实 key 才能运行管道。
    """
    import os
    from dotenv import load_dotenv
    load_dotenv()  # .env -> os.environ（pydantic-settings 只填 Settings 字段，不动 os.environ）
    registered: list[str] = []

    # MiniMax（Anthropic 兼容）
    minimax_key = os.environ.get("MINIMAX_API_KEY", "")
    if _is_real_key(minimax_key):
        api_base = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com/anthropic")
        model = os.environ.get("MINIMAX_MODEL", "MiniMax M3")
        register_provider("minimax", make_minimax_provider(minimax_key, api_base, model))
        registered.append("minimax")

    # DeepSeek（OpenAI 兼容）
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if _is_real_key(deepseek_key):
        api_base = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")
        model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        register_provider("deepseek", make_openai_provider("deepseek", api_base, deepseek_key, model))
        registered.append("deepseek")

    # 豆包（OpenAI 兼容，火山引擎）
    doubao_key = os.environ.get("DOUBAO_API_KEY", "")
    if _is_real_key(doubao_key):
        api_base = os.environ.get("DOUBAO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
        model = os.environ.get("DOUBAO_MODEL", "doubao-pro-32k")
        register_provider("doubao", make_openai_provider("doubao", api_base, doubao_key, model))
        registered.append("doubao")

    # 通义千问（OpenAI 兼容，阿里 DashScope）
    qwen_key = os.environ.get("QWEN_API_KEY", "")
    if _is_real_key(qwen_key):
        api_base = os.environ.get("QWEN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        model = os.environ.get("QWEN_MODEL", "qwen-plus")
        register_provider("qwen", make_openai_provider("qwen", api_base, qwen_key, model))
        registered.append("qwen")

    return registered


def list_providers() -> list[str]:
    """返回已注册的 provider 名列表"""
    return list(_registry.keys())


# OpenAI 兼容 provider 的默认 api_base / model（DB key 未填时兜底）
_OPENAI_DEFAULTS: dict[str, tuple[str, str]] = {
    "deepseek": ("https://api.deepseek.com", "deepseek-chat"),
    "doubao": ("https://ark.cn-beijing.volces.com/api/v3", "doubao-pro-32k"),
    "qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
}


async def auto_register_all(session) -> list[str]:
    """env 优先注册，再用 DB ApiKey 池补齐未注册的 provider（C0.8 平台托管）。

    用户不接触 .env：管理员把 key 录到 DB，本函数读 DB 补齐。env 已注册的 provider
    不被 DB 覆盖（env 优先，便于本地开发覆盖）。返回已注册名列表。
    """
    registered = auto_register_from_env()
    from sqlalchemy import select
    from ..db.models import ApiKey
    result = await session.execute(select(ApiKey).where(ApiKey.is_active == True))
    for row in result.scalars():
        if row.provider in _registry:
            continue  # env 已注册，跳过
        if not _is_real_key(row.api_key):
            continue
        if row.provider == "minimax":
            register_provider("minimax", make_minimax_provider(
                row.api_key,
                row.api_base or "https://api.minimaxi.com/anthropic",
                row.model or "MiniMax M3"))
            registered.append("minimax")
        elif row.provider in _OPENAI_DEFAULTS:
            base_default, model_default = _OPENAI_DEFAULTS[row.provider]
            register_provider(row.provider, make_openai_provider(
                row.provider,
                row.api_base or base_default,
                row.api_key,
                row.model or model_default))
            registered.append(row.provider)
    return registered
