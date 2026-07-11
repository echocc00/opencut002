"""场景检测 + 关键帧提取"""
from __future__ import annotations
import subprocess
import json
from pathlib import Path
from typing import Any


def detect_scenes(video_path: str | Path, threshold: float = 0.3) -> dict[str, Any]:
    """检测场景切换点"""
    video_path = Path(video_path)
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(video_path)]
    probe = json.loads(subprocess.check_output(cmd, timeout=15))
    duration = float(probe.get("format", {}).get("duration", 0))

    # 用ffmpeg检测场景切换
    cmd = ["ffmpeg", "-i", str(video_path), "-vf", f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"]
    output = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    scene_count = output.stderr.count("pts_time:")

    # 推断节奏
    if duration > 0:
        sps = scene_count / duration
        pacing = "fast" if sps > 0.5 else "medium" if sps > 0.2 else "slow"
    else:
        pacing = "unknown"

    return {"scene_count": scene_count, "duration": duration, "pacing": pacing}


def extract_keyframes(video_path: str | Path, output_dir: str | Path,
                      count: int = 6) -> list[str]:
    """提取关键帧"""
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(video_path)]
    probe = json.loads(subprocess.check_output(cmd, timeout=15))
    duration = float(probe.get("format", {}).get("duration", 0))

    frames = []
    for i in range(count):
        pos = duration * (i + 0.5) / count
        out = output_dir / f"keyframe_{i}.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(pos), "-i", str(video_path), "-vframes", "1", "-q:v", "2", str(out)],
            capture_output=True, timeout=15, check=True,
        )
        if out.exists():
            frames.append(str(out))
    return frames
