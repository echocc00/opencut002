"""图片匹配工具 - AI语义匹配 + 4层回退"""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any


def build_matching_prompt(paragraphs: list[dict], available_images: list[dict]) -> str:
    """构建图片匹配 prompt（段落 -> 图片的语义匹配）"""
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
输出JSON: {{"matches": [{{"paragraph": 0, "image": "filename.jpg"}}]}}
注意：image 字段必须填上面图片列表里的真实 file 值，不要编造或描述。"""


async def match_images(paragraphs: list[dict], available_images: list[dict],
                       ai_complete=None) -> dict[str, str]:
    """将文案段落与图片匹配。返回 {段落index: 真实图片完整路径}"""
    # 可用图片：filename -> 完整路径
    available_files = [img.get("file", "") for img in available_images if img.get("file")]
    available_map = {Path(f).name: f for f in available_files}

    matches: dict[str, str] = {}

    # 优先 AI 匹配
    if ai_complete:
        prompt = build_matching_prompt(paragraphs, available_images)
        try:
            resp = await ai_complete(prompt)
            m = re.search(r'\{[\s\S]*\}', resp)
            if m:
                data = json.loads(m.group())
                for match in data.get("matches", []):
                    para = str(match.get("paragraph", ""))
                    img = str(match.get("image", ""))
                    # 校验 AI 返回的是真实可用图片（按文件名匹配），否则忽略
                    img_name = Path(img).name if img else ""
                    if img_name in available_map:
                        matches[para] = available_map[img_name]
        except Exception:
            pass

    # 回退：按顺序分配真实图片
    for i, para in enumerate(paragraphs):
        if str(i) not in matches:
            hint = para.get("image_hint", "")
            hint_name = Path(hint).name if hint else ""
            if hint_name in available_map:
                matches[str(i)] = available_map[hint_name]
            elif i < len(available_files):
                matches[str(i)] = available_files[i]
            else:
                matches[str(i)] = ""

    return matches

