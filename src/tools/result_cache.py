"""结果缓存 - 基于输入 hash 的文件缓存

避免调试期 / 相同输入重复调 API（TTS、素材分析、文案等）。
命中时直接读本地文件，跳过 API 调用 -> 降本 + 加速。

开关：OPENCUT_CACHE=1 开启（默认关，避免开发期脏缓存）。
存储：data/cache/<kind>/<hash>.<ext>
  - kind: tts（.mp3）/ llm（.json）/ render（.mp4 + .json）
  - hash: sha256(规范化输入) 前 16 位

注意：缓存按"输入完全相同"命中。改了 prompt / voice_id / speed / 图片内容 都会 miss。
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def is_enabled() -> bool:
    """OPENCUT_CACHE=1 开启"""
    return os.environ.get("OPENCUT_CACHE", "").strip().lower() in ("1", "true", "yes", "on")


def make_key(*parts: Any) -> str:
    """由若干输入部分算缓存 key（sha256 前 16 位）。

    parts 可以是 str/int/bytes/Path。str 会去掉首尾空白规范化。
    """
    h = hashlib.sha256()
    for p in parts:
        if p is None:
            h.update(b"\x00")
        elif isinstance(p, bytes):
            h.update(p)
        elif isinstance(p, Path):
            # 文件路径：按内容 hash（同名文件改了内容也能 miss）
            h.update(str(p).encode("utf-8"))
            try:
                if p.exists():
                    h.update(p.read_bytes())
            except OSError:
                pass
        else:
            h.update(str(p).strip().encode("utf-8"))
        h.update(b"\x1f")  # 分隔符，防 "ab"+"c" == "a"+"bc"
    return h.hexdigest()[:16]


def _cache_dir(kind: str) -> Path:
    d = Path("data/cache") / kind
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_bytes(key: str, kind: str, ext: str) -> bytes | None:
    """命中返回 bytes，miss 返回 None。"""
    if not is_enabled():
        return None
    p = _cache_dir(kind) / f"{key}.{ext}"
    if p.exists():
        return p.read_bytes()
    return None


def set_bytes(key: str, kind: str, ext: str, content: bytes) -> None:
    """写入缓存。"""
    if not is_enabled():
        return
    p = _cache_dir(kind) / f"{key}.{ext}"
    p.write_bytes(content)


def get_json(key: str, kind: str) -> Any | None:
    """命中返回反序列化后的对象，miss 返回 None。"""
    if not is_enabled():
        return None
    p = _cache_dir(kind) / f"{key}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def set_json(key: str, kind: str, obj: Any) -> None:
    """写入 JSON 缓存。"""
    if not is_enabled():
        return
    p = _cache_dir(kind) / f"{key}.json"
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
