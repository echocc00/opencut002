"""验证 minimax M3 多模态：测 OpenAI 兼容 + Anthropic 兼容 image block 两条路径。

用法：python scripts/test_minimax_vision.py
"""
from __future__ import annotations
import base64
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv
import httpx

load_dotenv()
KEY = os.environ.get("MINIMAX_API_KEY", "")
MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax M3")
IMG = Path("data/projects/fuxue/materials/frame_01.jpg")

if not KEY:
    print("[X] MINIMAX_API_KEY 未配置"); sys.exit(1)
if not IMG.exists():
    print(f"[X] 测试图不存在: {IMG}"); sys.exit(1)

b64 = base64.b64encode(IMG.read_bytes()).decode()
print(f"测试图: {IMG} ({IMG.stat().st_size // 1024} KB) | 模型: {MODEL}\n")

PROMPT = "用一句话描述这张图的真实画面内容。"

# ---- 路径 A: OpenAI 兼容 /v1/chat/completions + image_url ----
print("=" * 60)
print("路径 A: OpenAI 兼容  https://api.minimaxi.com/v1/chat/completions")
print("=" * 60)
payload_a = {
    "model": MODEL,
    "messages": [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
    ]}],
    "max_tokens": 200,
}
try:
    r = httpx.post("https://api.minimaxi.com/v1/chat/completions",
                   headers={"Authorization": f"Bearer {KEY}",
                            "Content-Type": "application/json"},
                   json=payload_a, timeout=60)
    print(f"HTTP {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        print("回复:", d["choices"][0]["message"]["content"])
        u = d.get("usage", {})
        print(f"tokens: in={u.get('prompt_tokens')} out={u.get('completion_tokens')}")
        print("[OK] 路径 A 通")
    else:
        print(r.text[:500])
        print("[X] 路径 A 失败")
except Exception as e:
    print(f"[X] 异常: {e}")

# ---- 路径 B: Anthropic 兼容 /anthropic/v1/messages + image block ----
print()
print("=" * 60)
print("路径 B: Anthropic 兼容  https://api.minimaxi.com/anthropic/v1/messages")
print("=" * 60)
payload_b = {
    "model": MODEL,
    "max_tokens": 200,
    "messages": [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image", "source": {"type": "base64",
                                      "media_type": "image/jpeg", "data": b64}},
    ]}],
}
try:
    r = httpx.post("https://api.minimaxi.com/anthropic/v1/messages",
                   headers={"Content-Type": "application/json", "x-api-key": KEY},
                   json=payload_b, timeout=60)
    print(f"HTTP {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        print("回复:", d["content"][0]["text"])
        u = d.get("usage", {})
        print(f"tokens: in={u.get('input_tokens')} out={u.get('output_tokens')}")
        print("[OK] 路径 B 通")
    else:
        print(r.text[:500])
        print("[X] 路径 B 失败")
except Exception as e:
    print(f"[X] 异常: {e}")
