"""Provider 成本计算 - 基于 token 用量和单价表"""
from __future__ import annotations

import yaml
from pathlib import Path

_PRICING: dict | None = None


def load_pricing(path: str = "config/provider_pricing.yaml") -> dict:
    global _PRICING
    if _PRICING is None:
        p = Path(path)
        if p.exists():
            _PRICING = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        else:
            _PRICING = {}
    return _PRICING


def calc_cost(input_tokens: int, output_tokens: int, provider: str) -> float:
    """计算单次调用成本（美元）。无定价信息返回 0。"""
    pricing = load_pricing()
    p = pricing.get(provider, {})
    in_cost = input_tokens / 1000 * p.get("input_per_1k", 0.0)
    out_cost = output_tokens / 1000 * p.get("output_per_1k", 0.0)
    return round(in_cost + out_cost, 6)
