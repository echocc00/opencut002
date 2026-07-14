"""图片匹配工具 - AI 语义匹配 + 打分 + hint 兜底（缺口段不强制分配，交给分层决策）"""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any


def build_matching_prompt(paragraphs: list[dict], available_images: list[dict]) -> str:
    """构建图片匹配 prompt（段落 -> 图片的语义匹配 + relevance 打分）"""
    para_summary = [
        {"i": i, "text": p.get("text", ""), "hint": p.get("image_hint", "")}
        for i, p in enumerate(paragraphs)
    ]
    img_summary = [
        {"i": i, "scene": img.get("scene", ""), "file": img.get("file", "")}
        for i, img in enumerate(available_images)
    ]
    return f"""将文案段落与图片匹配。
段落: {json.dumps(para_summary, ensure_ascii=False)}
图片: {json.dumps(img_summary, ensure_ascii=False)}
输出JSON: {{"matches": [{{"paragraph": 0, "image": "filename.jpg", "relevance": 0.8}}]}}
注意：
- image 字段必须填上面图片列表里的真实 file 值，不要编造或描述。
- relevance 是该段落与图片的语义相关度，0-1 浮点（1=完全匹配，0=无关）。
- 只返回相关度 >= 0.3 的匹配，无关段落不要硬配。"""


async def match_images(paragraphs: list[dict], available_images: list[dict],
                       ai_complete=None) -> dict[str, dict[str, Any]]:
    """将文案段落与图片匹配 + 打分。

    返回 {段落index(str): {"image": 完整路径, "score": 0-1}}。
    AI 匹配 + relevance 打分；hint 兜底（显式 hint 视为强匹配 score=1.0）；
    缺口段（无 AI 匹配、无 hint）image="" score=0.0，不强制分配，交给分层决策。
    """
    available_files = [img.get("file", "") for img in available_images if img.get("file")]
    available_map = {Path(f).name: f for f in available_files}

    matches: dict[str, dict[str, Any]] = {}

    # 1. AI 匹配 + 打分
    if ai_complete:
        prompt = build_matching_prompt(paragraphs, available_images)
        try:
            resp = await ai_complete(prompt)
            m = re.search(r'\{[\s\S]*\}', resp.text if hasattr(resp, "text") else str(resp))
            if m:
                data = json.loads(m.group())
                for match in data.get("matches", []):
                    para = str(match.get("paragraph", ""))
                    img_name = Path(str(match.get("image", ""))).name
                    try:
                        score = float(match.get("relevance", 0.5))
                    except (TypeError, ValueError):
                        score = 0.5
                    score = max(0.0, min(1.0, score))
                    if para and img_name in available_map:
                        matches[para] = {"image": available_map[img_name], "score": score}
        except Exception:
            pass

    # 2. hint 兜底（显式 hint = 强匹配）
    for i, para in enumerate(paragraphs):
        if str(i) not in matches:
            hint = para.get("image_hint", "")
            hint_name = Path(hint).name if hint else ""
            if hint_name in available_map:
                matches[str(i)] = {"image": available_map[hint_name], "score": 1.0}

    # 3. 缺口段：image="", score=0.0（不强制分配，交给 ImageMatchingAgent 分层决策）
    for i in range(len(paragraphs)):
        if str(i) not in matches:
            matches[str(i)] = {"image": "", "score": 0.0}

    return matches
