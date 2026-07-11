"""Web 搜索工具 - DuckDuckGo Instant Answer API"""
from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)


async def search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """执行搜索，DuckDuckGo优先，Bing备选"""
    results: list[dict[str, Any]] = []

    # 1. DuckDuckGo
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            )
            if resp.status_code == 200:
                data = resp.json()
                abstract = data.get("AbstractText", "")
                if abstract:
                    results.append({"query": query, "source": "duckduckgo", "text": abstract[:300]})
                for topic in data.get("RelatedTopics", [])[:max_results]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        results.append({"query": query, "source": "duckduckgo", "text": topic["Text"][:300]})
    except Exception as e:
        log.warning(f"DuckDuckGo搜索失败 [{query}]: {e}")

    # 2. 如果DuckDuckGo无结果，尝试Bing（需要API key）
    if not results:
        import os
        bing_key = os.environ.get("BING_API_KEY", "")
        if bing_key:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        "https://api.bing.microsoft.com/v7.0/search",
                        headers={"Ocp-Apim-Subscription-Key": bing_key},
                        params={"q": query, "count": max_results},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in data.get("webPages", {}).get("value", [])[:max_results]:
                            results.append({"query": query, "source": "bing", "text": item.get("snippet", "")[:300]})
            except Exception as e:
                log.warning(f"Bing搜索失败 [{query}]: {e}")

    return results


async def batch_search(queries: list[str], max_per_query: int = 3) -> list[dict[str, Any]]:
    """批量搜索多个查询"""
    all_results: list[dict[str, Any]] = []
    for q in queries:
        results = await search(q, max_per_query)
        all_results.extend(results)
    return all_results
