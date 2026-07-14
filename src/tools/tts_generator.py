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
                               emotion: str = "", speed: float = 1.0,
                               api_key: str = "",
                               api_base: str = "https://api.minimaxi.com") -> str:
    """MiniMax 同步 TTS (t2a_v2)：响应 data.audio 是 hex-encoded MP3，Bearer 鉴权，无轮询。

    emotion: minimax 语气取值（happy/sad/angry/fearful/disgusted/surprised/neutral），
             空字符串则不传（用 minimax 默认）。
    speed: 语速倍率，默认 1.0（minimax 默认）。如需加速可显式传 1.2 等。
    """
    from pathlib import Path as _Path
    output_path = _Path(output_path)
    import httpx

    # 结果缓存（OPENCUT_CACHE=1 开启）：相同 (text, voice_id, emotion, speed) 命中跳过 API
    from .result_cache import make_key, get_bytes, set_bytes
    cache_key = make_key(text, voice_id, emotion, speed)
    cached = get_bytes(cache_key, "tts", "mp3")
    if cached is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(cached)
        return str(output_path)

    api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        raise RuntimeError("无 MINIMAX_API_KEY")

    voice_setting: dict = {"voice_id": voice_id, "speed": speed, "vol": 1, "pitch": 1}
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
        r = await client.post(f"{api_base}/v1/t2a_v2", headers=headers, json=body)
        if r.status_code != 200:
            raise RuntimeError(f"MiniMax TTS 失败 {r.status_code}: {r.text[:200]}")
        audio_hex = r.json().get("data", {}).get("audio")
        if not audio_hex:
            raise RuntimeError(f"MiniMax TTS 无 audio: {r.text[:200]}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    audio_bytes = bytes.fromhex(audio_hex)
    output_path.write_bytes(audio_bytes)
    set_bytes(cache_key, "tts", "mp3", audio_bytes)
    return str(output_path)


async def generate_tts(text: str, voice: str, output_path: str | Path,
                       engine: str = "minimax", emotion: str = "",
                       speed: float = 1.0) -> str:
    """生成TTS音频。engine: minimax（默认，异步 t2a_async_v2）或 edge-tts。
    emotion: minimax 语气取值（仅 minimax 引擎生效）。
    speed: 语速倍率（仅 minimax 引擎生效，默认 1.0）。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if engine == "minimax":
        # edge voice 映射到 minimax voice_id；未映射的（如克隆 voice_id）直传
        voice_id = EDGE_TO_MINIMAX_VOICE.get(voice, voice)
        return await generate_tts_minimax(text, voice_id, output_path, emotion=emotion, speed=speed)

    if engine == "edge-tts":
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(output_path))
        return str(output_path)

    raise ValueError(f"不支持的TTS引擎: {engine}")


async def clone_voice_minimax(audio_path: Path, voice_id: str,
                              api_key: str = "",
                              api_base: str = "https://api.minimaxi.com") -> dict:
    """上传参考音频克隆音色。voice_id 是自定义音色 ID，TTS 时用此 ID 合成。

    流程：1) /v1/files/upload 上传音频得 file_id  2) /v1/voice_clone 传 voice_id + file_id。
    克隆完成后，generate_tts_minimax 直接用该 voice_id 合成。
    """
    import httpx
    api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        raise RuntimeError("无 MINIMAX_API_KEY")

    async with httpx.AsyncClient(timeout=120) as client:
        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "audio/mpeg")}
            data = {"purpose": "voice_clone"}
            r = await client.post(f"{api_base}/v1/files/upload",
                                  headers={"Authorization": f"Bearer {api_key}"},
                                  files=files, data=data)
        if r.status_code != 200:
            raise RuntimeError(f"克隆上传失败 {r.status_code}: {r.text[:200]}")
        file_id = r.json().get("file", {}).get("file_id")
        if not file_id:
            raise RuntimeError(f"克隆上传无 file_id: {r.text[:200]}")

        r2 = await client.post(
            f"{api_base}/v1/voice_clone",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={"voice_id": voice_id, "file_id": file_id},
        )
        ok = r2.status_code == 200 and r2.json().get("base_resp", {}).get("status_code") == 0
        if not ok:
            raise RuntimeError(f"克隆失败 {r2.status_code}: {r2.text[:200]}")

    return {"success": True, "voice_id": voice_id, "file_id": file_id}
