"""验证 minimax image-01 生图 API + generate_image 封装（真实 key 调一次）

minimax 是国内 API，无需代理。打印原始响应确认字段结构，再测封装。
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv
load_dotenv()

import httpx


async def test_raw_api():
    """直接调 minimax image gen API，打印响应确认结构"""
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        print("[X] 无 MINIMAX_API_KEY")
        return None
    body = {
        "model": "image-01",
        "prompt": "一只可爱的橘猫坐在教室课桌上，纪实摄影风格，暖色调，竖构图",
        "aspect_ratio": "9:16",
        "n": 1,
    }
    print(f"[1] POST /v1/image/generation  model=image-01")
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            "https://api.minimaxi.com/v1/image_generation",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        )
    print(f"    status: {r.status_code}")
    print(f"    response: {r.text[:800]}")
    return r


async def test_wrapper():
    """测我们的 generate_image 封装"""
    from src.tools.image_generator import generate_image
    ma_output = {"images": [{"scene": "教室室内，暖色调，纪实摄影"}, {"scene": "学生听课"}]}
    print("\n[2] 调 generate_image() 封装")
    try:
        path = await generate_image("一只橘猫在教室里", ma_output, "verify_gen", 0)
        print(f"    [OK] 生成图: {path}")
        import os
        if os.path.exists(path):
            print(f"    文件大小: {os.path.getsize(path)} bytes")
        return path
    except Exception as e:
        print(f"    [FAIL] {e}")
        return None


async def main():
    await test_raw_api()
    await test_wrapper()


if __name__ == "__main__":
    asyncio.run(main())
