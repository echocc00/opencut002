"""生成可爱拟人化 3D 卡通头像贴纸（minimax 生图 + rembg 去背景 -> 透明 PNG）

一次性生成，结果存 src/tools/stickers/cute_*.png，face_masker 直接用。
rembg 仅生成时用（不进运行时依赖）。
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

from PIL import Image
from rembg import remove
from src.tools.image_generator import generate_image

PROMPTS = [
    "一个可爱的3D卡通小男孩头像，大眼睛，开心微笑，圆润拟人化风格，正面居中，纯白背景",
    "一个可爱的3D卡通小女孩头像，大眼睛，调皮笑容，圆润拟人化风格，正面居中，纯白背景",
    "一个可爱的3D卡通小熊角色头像，拟人化开心表情，大眼睛，圆润，正面居中，纯白背景",
    "一个可爱的3D卡通小兔子角色头像，拟人化表情，大眼睛，圆润，正面居中，纯白背景",
    "一个可爱的3D卡通小猫角色头像，拟人化笑容，大眼睛，圆润，正面居中，纯白背景",
    "一个可爱的3D卡通机器人头像，拟人化友好表情，大眼睛，圆润，正面居中，纯白背景",
]


async def main():
    ma = {"images": [{"scene": "可爱3D卡通头像，圆润拟人化"}]}
    out_dir = "src/tools/stickers"
    os.makedirs(out_dir, exist_ok=True)
    for i, prompt in enumerate(PROMPTS):
        try:
            path = await generate_image(prompt, ma, "gen_stickers", i)
            img = Image.open(path).convert("RGB")
            # rembg 去背景 -> 透明 PNG
            result = remove(img)
            # 裁成正方形 + 缩到 512
            w, h = result.size
            s = min(w, h)
            result = result.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))
            result = result.resize((512, 512), Image.LANCZOS)
            out_path = os.path.join(out_dir, f"cute_{i}.png")
            result.save(out_path, "PNG")
            print(f"[OK] cute_{i}.png ({result.size})")
        except Exception as e:
            print(f"[FAIL] {i}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
