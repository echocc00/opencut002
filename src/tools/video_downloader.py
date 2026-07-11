"""视频下载工具 - yt-dlp"""
from __future__ import annotations
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


def download_video(url: str, output_path: str | Path | None = None,
                   max_height: int = 720) -> Optional[str]:
    """下载视频，返回本地路径"""
    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix=".mp4"))
    else:
        output_path = Path(output_path)

    try:
        subprocess.run(
            ["yt-dlp", "-f", f"best[height<={max_height}]", "-o", str(output_path), url],
            capture_output=True, timeout=120, check=True,
        )
        return str(output_path) if output_path.exists() else None
    except Exception:
        return None
