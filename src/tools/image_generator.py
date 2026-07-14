"""AI 生图工具（第3层兜底，opt-in OPENCUT_IMAGE_GEN=1）

为缺口段落生成与素材池风格一致的图：prompt = 段落内容 + 池风格描述（从 material_analysis 聚合）。
用 minimax image-01（复用 MINIMAX_API_KEY）。生图失败由 ImageMatchingAgent 回退到文字卡。

注意：minimax image generation API 的请求/响应字段以官方文档为准，这里按常见形态实现 +
多路径兼容。首次启用需用真实 key 验证响应解析（失败会自动回退文字卡，不影响出片）。
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_MINIMAX_API_BASE = "https://api.minimaxi.com"


def _pool_style_descriptor(ma_output: dict) -> str:
    """从 material_analysis 聚合池图风格描述，作为生图风格提示"""
    scenes = [img.get("scene", "") for img in ma_output.get("images", []) if img.get("scene")]
    if not scenes:
        return ""
    return "、".join(scenes[:3])


async def generate_image(paragraph_text: str, ma_output: dict,
                         project_id: str, index: int) -> str:
    """为段落生成图，下载到 data/projects/<id>/generated/gen_<i>.jpg，返回路径。

    Raises: RuntimeError（无 key / API 失败 / 无 url）-> 调用方回退文字卡。
    """
    import httpx
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        raise RuntimeError("无 MINIMAX_API_KEY，无法生图")

    style = _pool_style_descriptor(ma_output)
    prompt = f"{paragraph_text}。风格：{style}" if style else paragraph_text
    body = {"model": "image-01", "prompt": prompt, "aspect_ratio": "9:16", "n": 1}

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{_MINIMAX_API_BASE}/v1/image/generation",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        )
        if r.status_code != 200:
            raise RuntimeError(f"生图 API 失败 {r.status_code}: {r.text[:200]}")
        data = r.json()

    # 响应 url 路径兼容（minimax 可能返回 data.image_urls / images / data.images）
    urls = (
        (data.get("data", {}) or {}).get("image_urls")
        or data.get("images")
        or (data.get("data", {}) or {}).get("images")
        or []
    )
    if not urls:
        raise RuntimeError(f"生图无 url: {str(data)[:200]}")
    url = urls[0] if isinstance(urls, list) else str(urls)

    out_dir = Path(f"data/projects/{project_id}/generated")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"gen_{index}.jpg"
    async with httpx.AsyncClient(timeout=60) as client:
        r2 = await client.get(url)
        if r2.status_code != 200:
            raise RuntimeError(f"下载生图失败 {r2.status_code}")
        out_path.write_bytes(r2.content)
    log.info("生图段落%d -> %s", index, out_path)
    return str(out_path)
