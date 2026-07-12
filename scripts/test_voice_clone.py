"""验证 minimax voice cloning API（upload_clone_audio）格式。

用法：python scripts/test_voice_clone.py
用 fuxue_emotion 的合成音频作参考音频，测 API 接受性。
"""
from __future__ import annotations
import asyncio
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, ".")
from dotenv import load_dotenv
import httpx

load_dotenv()
KEY = os.environ.get("MINIMAX_API_KEY", "")
AUDIO = Path("data/projects/fuxue_emotion/audio/voice.mp3")
VOICE_ID = "oc_test_001"


async def main() -> None:
    if not AUDIO.exists():
        print(f"[X] 参考音频不存在: {AUDIO}"); sys.exit(1)
    print(f"参考音频: {AUDIO} ({AUDIO.stat().st_size // 1024} KB)")
    print(f"voice_id: {VOICE_ID}\n")

    async with httpx.AsyncClient(timeout=120) as client:
        # 1. 上传音频文件得 file_id（试多个端点）
        upload_paths = ["/v1/files/upload", "/v1/files", "/v1/files/create_file"]
        file_id = ""
        for up in upload_paths:
            with open(AUDIO, "rb") as f:
                files = {"file": (AUDIO.name, f, "audio/mpeg")}
                data = {"purpose": "voice_clone"}
                r = await client.post(
                    f"https://api.minimaxi.com{up}",
                    headers={"Authorization": f"Bearer {KEY}"},
                    files=files, data=data,
                )
            print(f"[上传] {up} HTTP {r.status_code}: {r.text[:200]}")
            if r.status_code == 200:
                try:
                    file_id = r.json().get("file", {}).get("file_id", "") or r.json().get("file_id", "")
                except Exception:
                    pass
                if file_id:
                    print(f"  -> file_id={file_id}")
                    break
        if not file_id:
            print("\n[X] 未拿到 file_id，停止"); return

        # 2. voice_clone 传 voice_id + file_id
        r2 = await client.post(
            "https://api.minimaxi.com/v1/voice_clone",
            headers={"Authorization": f"Bearer {KEY}",
                     "Content-Type": "application/json"},
            json={"voice_id": VOICE_ID, "file_id": file_id},
        )
        print(f"[克隆] /v1/voice_clone HTTP {r2.status_code}: {r2.text[:500]}")


if __name__ == "__main__":
    asyncio.run(main())
