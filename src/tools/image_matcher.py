"""图片匹配工具 - AI语义匹配 + 4层回退"""
from __future__ import annotations
from typing import Any

async def match_images(paragraphs: list[dict], available_images: list[dict],
                       ai_complete=None) -> dict[str, str]:
    """将文案段落与图片匹配"""
    matches: dict[str, str] = {}

    # 优先尝试AI匹配
    if ai_complete:
        import json
        prompt = f"""将文案段落与图片匹配。
段落: {json.dumps([{{"i": i, "text": p.get("text",""), "hint": p.get("image_hint","")}} for i,p in enumerate(paragraphs)], ensure_ascii=False)}
图片: {json.dumps([{{"i": i, "scene": img.get("scene",""), "file": img.get("file","")}} for i,img in enumerate(available_images)], ensure_ascii=False)}
输出JSON: {{"matches": [{{"paragraph": 0, "image": "filename.jpg"}}]}}"""
        try:
            resp = await ai_complete(prompt)
            import re
            m = re.search(r'\{[\s\S]*\}', resp)
            if m:
                data = json.loads(m.group())
                for match in data.get("matches", []):
                    matches[str(match["paragraph"])] = match["image"]
        except Exception:
            pass

    # 回退：按顺序分配
    for i, para in enumerate(paragraphs):
        if str(i) not in matches:
            hint = para.get("image_hint", "")
            if hint:
                matches[str(i)] = hint
            elif i < len(available_images):
                matches[str(i)] = available_images[i].get("file", f"img_{i}.jpg")
            else:
                matches[str(i)] = ""  # 空镜

    return matches
