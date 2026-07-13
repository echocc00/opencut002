"""素材准备工具 - 收集图片 + 视频自动抽帧

run_full.py 和 api/ 上传接口共用：把素材目录里的图片和视频统一成
[{file, filename}] 列表供 material_analysis_agent 消费。
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


def prepare_materials(
    mat_dir: str | Path,
    max_count: int = 5,
    fps: float = 0.2,
) -> list[dict[str, str]]:
    """收集素材目录里的图片 + 视频抽帧，返回 [{file, filename}] 列表。

    - 图片：*.jpg/*.jpeg/*.png 直接收录（大小写不敏感）
    - 视频：*.mp4/*.mov/*.avi/*.mkv/*.webm/*.m4v 用 ffmpeg 每 1/fps 秒抽一帧
      到 .frames/<video_stem>/frame_%03d.jpg（fps=0.2 即每 5 秒一帧）
    - ffmpeg 不存在或抽帧失败时跳过该视频（不阻断整体）
    - 按文件名排序，图片优先于视频抽帧，取前 max_count 张
    """
    mat_dir = Path(mat_dir)
    images: list[Path] = []
    videos: list[Path] = []
    for p in sorted(mat_dir.iterdir(), key=lambda x: x.name.lower()):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in IMAGE_EXTS:
            images.append(p)
        elif ext in VIDEO_EXTS:
            videos.append(p)

    frame_images = _extract_frames(mat_dir, videos, fps)

    all_images = images + frame_images
    return [{"file": str(p.resolve()), "filename": p.name} for p in all_images[:max_count]]


def _extract_frames(mat_dir: Path, videos: list[Path], fps: float) -> list[Path]:
    """对每个视频用 ffmpeg 抽帧到 .frames/<stem>/，返回所有抽出的 jpg 路径。"""
    if not videos:
        return []
    if not shutil.which("ffmpeg"):
        log.warning("未找到 ffmpeg，跳过视频抽帧（%d 个视频未处理）", len(videos))
        return []

    frames_root = mat_dir / ".frames"
    all_frames: list[Path] = []
    for vid in videos:
        out_dir = frames_root / vid.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        # 清理旧帧避免不同次运行累积
        for old in out_dir.glob("frame_*.jpg"):
            old.unlink()
        cmd = [
            "ffmpeg", "-y", "-i", str(vid),
            "-vf", f"fps={fps}", "-q:v", "3",
            str(out_dir / "frame_%03d.jpg"),
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=180, check=True)
            frames = sorted(out_dir.glob("frame_*.jpg"))
            all_frames.extend(frames)
            log.info("视频 %s 抽出 %d 帧", vid.name, len(frames))
        except subprocess.CalledProcessError as e:
            log.warning("视频 %s 抽帧失败 (exit %d): %s", vid.name, e.returncode,
                        (e.stderr or b"").decode("utf-8", errors="replace")[-200:])
        except subprocess.TimeoutExpired:
            log.warning("视频 %s 抽帧超时（>180s）", vid.name)
    return all_frames
