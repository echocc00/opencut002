"""验证 minimax TTS 带 emotion 是否生效（happy/sad/neutral/angry/surprised）。

用法：python scripts/test_tts_emotion.py
"""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, ".")
from dotenv import load_dotenv
from src.tools.tts_generator import generate_tts_minimax

load_dotenv()

CASES = [
    ("happy", "今天给大家分享一个超级棒的学习方法，让你事半功倍！"),
    ("sad", "这次考试又没考好，心里真的很难过。"),
    ("angry", "这种粗心大意的错误，绝对不能再犯第二次！"),
    ("surprised", "你绝对想不到，这个方法居然这么有效！"),
    ("neutral", "下面我们来看一下这道题的解题步骤。"),
]

OUT_DIR = Path("data/projects/_tts_emotion_test")


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for emotion, text in CASES:
        out = OUT_DIR / f"voice_{emotion}.mp3"
        try:
            await generate_tts_minimax(text, "audiobook_male_1", out, emotion=emotion)
            print(f"[OK] {emotion:10s} {out.stat().st_size // 1024} KB | {text}")
        except Exception as e:
            print(f"[X] {emotion:10s} 失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
