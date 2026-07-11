"""TTS 生成工具 - Edge-TTS / MiniMax"""
from __future__ import annotations
import logging
from pathlib import Path

log = logging.getLogger(__name__)

async def generate_tts(text: str, voice: str, output_path: str | Path,
                       engine: str = "edge-tts") -> str:
    """生成TTS音频"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if engine == "edge-tts":
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_path))
            return str(output_path)
        except Exception as e:
            log.error(f"Edge-TTS失败: {e}")
            # fallback: 用ffmpeg生成静音音频
            import subprocess
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                 "-t", str(max(len(text) * 0.3, 1)), "-c:a", "pcm_s16le", str(output_path)],
                capture_output=True, check=True,
            )
            return str(output_path)
    raise ValueError(f"不支持的TTS引擎: {engine}")
