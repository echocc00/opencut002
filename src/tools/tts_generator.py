"""TTS 生成工具 - MiniMax 异步 TTS (t2a_async_v2，默认) / Edge-TTS"""
from __future__ import annotations
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

# edge-tts 音色 -> minimax async TTS voice_id（speech-2.8-hd 用 audiobook 系列）
EDGE_TO_MINIMAX_VOICE = {
    "zh-CN-YunxiNeural": "audiobook_male_1",      # 磁性男声
    "zh-CN-YunyangNeural": "audiobook_male_1",    # 温暖男声
    "zh-CN-YunjianNeural": "audiobook_male_1",    # 沉稳男声
    "zh-CN-YunfengNeural": "audiobook_male_1",    # 阳光男声
    "zh-CN-XiaoyiNeural": "audiobook_female_1",   # 甜美女声
    "zh-CN-XiaochenNeural": "audiobook_female_1", # 温柔女声
    "zh-CN-XiaohanNeural": "audiobook_female_1",  # 知性女声
}
DEFAULT_MINIMAX_VOICE = "audiobook_male_1"


async def generate_tts_minimax(text: str, voice_id: str, output_path: Path,
                               emotion: str = "", api_key: str = "",
                               api_base: str = "https://api.minimaxi.com") -> str:
    """MiniMax 异步 TTS (t2a_async_v2)：create -> poll retrieve -> download tar -> extract mp3。

    不需要 GroupId（异步端点用 Bearer token 鉴权）。
    emotion: minimax 语气取值（happy/sad/angry/fearful/disgusted/surprised/neutral），
             空字符串则不传（用 minimax 默认）。
    """
    import asyncio, httpx, tarfile, io
    api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        raise RuntimeError("无 MINIMAX_API_KEY")

    voice_setting: dict = {"voice_id": voice_id, "speed": 1, "vol": 1, "pitch": 1}
    if emotion:
        voice_setting["emotion"] = emotion
    body = {
        "model": "speech-2.8-hd",
        "text": text,
        "voice_setting": voice_setting,
        "audio_setting": {"audio_sample_rate": 32000, "bitrate": 128000, "format": "mp3", "channel": 2},
        "language_boost": "auto",
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=120) as client:
        # 1. 创建任务
        r = await client.post(f"{api_base}/v1/t2a_async_v2", headers=headers, json=body)
        if r.status_code != 200:
            raise RuntimeError(f"MiniMax TTS 创建失败 {r.status_code}: {r.text[:200]}")
        file_id = r.json().get("file_id")
        if not file_id:
            raise RuntimeError(f"MiniMax TTS 无 file_id: {r.text[:200]}")

        # 2. 轮询文件就绪（最多 90s）
        for _ in range(30):
            await asyncio.sleep(3)
            r2 = await client.get(f"{api_base}/v1/files/retrieve?file_id={file_id}",
                                  headers={"Authorization": f"Bearer {api_key}"})
            f = r2.json().get("file")
            if f and f.get("download_url"):
                # 3. 下载 tar 包
                r3 = await client.get(f["download_url"])
                if r3.status_code != 200:
                    raise RuntimeError(f"MiniMax TTS 下载失败 {r3.status_code}")
                # 4. 从 tar 提取 mp3
                t = tarfile.open(fileobj=io.BytesIO(r3.content))
                for name in t.getnames():
                    if name.endswith(".mp3"):
                        output_path.write_bytes(t.extractfile(name).read())
                        return str(output_path)
                raise RuntimeError(f"MiniMax TTS tar 中无 mp3: {t.getnames()}")
        raise RuntimeError("MiniMax TTS 轮询超时（90s 文件未就绪）")


async def generate_tts(text: str, voice: str, output_path: str | Path,
                       engine: str = "minimax", emotion: str = "") -> str:
    """生成TTS音频。engine: minimax（默认，异步 t2a_async_v2）或 edge-tts。
    emotion: minimax 语气取值（仅 minimax 引擎生效）。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if engine == "minimax":
        voice_id = EDGE_TO_MINIMAX_VOICE.get(voice, DEFAULT_MINIMAX_VOICE)
        return await generate_tts_minimax(text, voice_id, output_path, emotion=emotion)

    if engine == "edge-tts":
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(output_path))
        return str(output_path)

    raise ValueError(f"不支持的TTS引擎: {engine}")
