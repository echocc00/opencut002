"""克隆音色：上传参考音频生成自定义 voice_id。

用法：
  python scripts/clone_voice.py --audio <参考音频.mp3> --voice-id <自定义ID>

克隆成功后，把 voice_id 配到 domains/<domain>/voices.json：
  {"my_voice": {"name": "我的克隆音色", "minimax_voice_id": "<自定义ID>", "description": "..."}}

然后 voice_selection 阶段可选该音色，TTS 用克隆音色合成（支持 emotion 语气）。
"""
from __future__ import annotations
import argparse
import asyncio
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, ".")
from dotenv import load_dotenv
from src.tools.tts_generator import clone_voice_minimax

load_dotenv()


async def main(audio: str, voice_id: str) -> None:
    p = Path(audio)
    if not p.exists():
        print(f"[X] 参考音频不存在: {p}"); sys.exit(1)
    print(f"克隆音色: {p} ({p.stat().st_size // 1024} KB) -> voice_id={voice_id}")
    result = await clone_voice_minimax(p, voice_id)
    print(f"[OK] 克隆成功！voice_id={result['voice_id']} file_id={result['file_id']}")
    print(f"\n配到 domains/<domain>/voices.json：")
    print(f'  "{voice_id}": {{"name": "克隆音色", "minimax_voice_id": "{voice_id}", '
          f'"description": "克隆自 {p.name}"}}')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="minimax 音色复刻")
    parser.add_argument("--audio", required=True,
                        help="参考音频路径（mp3/wav，建议 10-30s 清晰人声）")
    parser.add_argument("--voice-id", required=True,
                        help="自定义音色 ID（英文/数字/下划线，如 my_voice_01）")
    args = parser.parse_args()
    asyncio.run(main(args.audio, args.voice_id))
