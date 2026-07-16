"""Provider 故障转移链（v0.6.1，port 自 v0.5.4 audit + 安全修复）。

主 provider 失败（限流/网络/auth）时自动 fallback 到下一个配置的 provider。
区分瞬时（重试/转移）vs 永久（auth/坏请求 - 不转移，避免无意义重试 + 防 prompt 泄漏）。

安全修复（评审 MEDIUM）：
- _is_transient_error 拓宽 auth 检测：getattr(exc,"status_code") + exc.response.status_code
  + openai.AuthenticationError/PermissionDeniedError + minimax 通用 RuntimeError 的消息启发式
  （"API错误 401/403"）。401/403 判永久 -> 不 fallback，surface auth 问题
- 删死参数 min_attempts
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from .provider_registry import get_provider, ProviderResponse

log = logging.getLogger(__name__)


# 永久错误（不 fallback）：auth、坏请求、类型错误
PERMANENT_EXCEPTIONS = (
    ValueError,
    TypeError,
    KeyError,
    PermissionError,
)


def _status_code_from_exc(exc: Exception) -> Optional[int]:
    """从异常里尽力抠 HTTP status code（兼容 httpx / openai / 通用异常）。"""
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code
    resp = getattr(exc, "response", None)
    if resp is not None:
        code = getattr(resp, "status_code", None)
        if isinstance(code, int):
            return code
    return None


def _is_openai_auth_error(exc: Exception) -> bool:
    """openai SDK 的 auth/permission 异常（结构化，status_code=401/403）。"""
    try:
        from openai import AuthenticationError, PermissionDeniedError
        return isinstance(exc, (AuthenticationError, PermissionDeniedError))
    except Exception:
        return False


def _is_transient_error(exc: Exception) -> bool:
    """瞬时 -> fallback；永久（auth/4xx 坏请求）-> 不 fallback。"""
    if isinstance(exc, PERMANENT_EXCEPTIONS):
        return False
    if _is_openai_auth_error(exc):
        return False
    code = _status_code_from_exc(exc)
    if code is not None:
        # 4xx（除 408 超时、429 限流）= 永久（坏请求/auth），不 fallback
        if 400 <= code < 500 and code not in (408, 429):
            return False
        return True
    # 通用异常（如 minimax 的 RuntimeError("MiniMax API错误 401: ...")）按消息启发式
    msg = str(exc)
    if "API错误 401" in msg or "API错误 403" in msg:
        return False
    # 默认当瞬时（5xx / 网络 / 未知），fallback
    return True


async def call_with_fallback(
    prompt: str,
    providers: list[str],
    images: list[str] | None = None,
    max_tokens: int = 8192,
    max_attempts: Optional[int] = None,
    retry_delay: float = 0.5,
    fallback_on_empty: bool = True,
) -> ProviderResponse:
    """按顺序试 providers，瞬时错误/空响应 -> 下一个；永久错误 -> 立即 raise。

    Args:
        prompt: 提示文本
        providers: 有序 provider 名列表（如 ["minimax", "doubao"]）
        images: 多模态图片路径列表
        max_tokens: 最大生成 token
        max_attempts: 最多尝试数（默认 len(providers)）
        retry_delay: 尝试间隔秒
        fallback_on_empty: 空响应是否 fallback
    """
    if not providers:
        raise ValueError("providers list cannot be empty")

    attempts = max_attempts or len(providers)
    last_error: Exception | None = None
    empty_count = 0

    for i, provider_name in enumerate(providers[:attempts]):
        try:
            log.info(f"尝试 provider {provider_name}（{i + 1}/{attempts}）")
            provider = get_provider(provider_name)
            response = await provider.complete(prompt, images=images, max_tokens=max_tokens)
            text = (response.text or "").strip()
            if not text and fallback_on_empty:
                log.warning(f"provider {provider_name} 返回空，试下一个")
                empty_count += 1
                continue
            return response
        except Exception as e:
            last_error = e
            if not _is_transient_error(e):
                log.error(f"provider {provider_name} 永久错误: {e}，不 fallback")
                raise
            log.warning(f"provider {provider_name} 瞬时错误: {e}，试下一个")
            if i < len(providers) - 1 and retry_delay > 0:
                await asyncio.sleep(retry_delay)

    if empty_count and not last_error:
        raise RuntimeError(f"全部 {attempts} 个 provider 返回空响应")
    raise RuntimeError(f"全部 {attempts} 个 provider 失败，最后错误: {last_error}")


async def get_provider_with_fallback(
    prompt: str, providers: list[str], images: list[str] | None = None,
    max_tokens: int = 8192,
) -> ProviderResponse:
    """便捷包装：等价 call_with_fallback(prompt, providers, images, max_tokens)。"""
    return await call_with_fallback(
        prompt=prompt, providers=providers, images=images, max_tokens=max_tokens,
    )
