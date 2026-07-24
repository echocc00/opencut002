"""素材准备工具 - 收集图片 + 视频自动抽帧

run_full.py 和 api/ 上传接口共用：把素材目录里的图片和视频统一成
[{file, filename}] 列表供 material_analysis_agent 消费。

v0.6.4 素材多样性（借鉴第三方 fork Level A，opt-in）：
- diversity=True 时按帧间像素差选 top-k 差异最大的帧（避免都是首帧 frame_001.jpg）
- max_per_video 限制单个视频贡献帧数（避免短视频堆满候选）
默认 diversity=False / max_per_video=None，行为与 v0.6.3 完全一致；
run_full.py 读 OPENCUT_MATERIAL_DIVERSITY=1 时才开启（diversity=True + max_per_video=3）。
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}

# 多样性抽帧默认每视频贡献帧数（OPENCUT_MATERIAL_DIVERSITY=1 时启用）
DIVERSITY_MAX_PER_VIDEO = 3


def diversity_enabled() -> bool:
    """OPENCUT_MATERIAL_DIVERSITY=1 开启帧间差异选帧（默认关）。"""
    return os.environ.get("OPENCUT_MATERIAL_DIVERSITY", "").strip() in {"1", "true", "yes", "on"}


def prepare_materials(
    mat_dir: str | Path,
    max_count: int = 5,
    fps: float = 0.2,
    max_per_video: int | None = None,
    diversity: bool = False,
) -> list[dict[str, str]]:
    """收集素材目录里的图片 + 视频抽帧，返回 [{file, filename}] 列表。

    - 图片：*.jpg/*.jpeg/*.png 直接收录（大小写不敏感）
    - 视频：*.mp4/*.mov/*.avi/*.mkv/*.webm/*.m4v 用 ffmpeg 每 1/fps 秒抽一帧
      到 .frames/<video_stem>/frame_%03d.jpg（fps=0.2 即每 5 秒一帧）
    - ffmpeg 不存在或抽帧失败时跳过该视频（不阻断整体）
    - max_per_video：每个视频最多贡献 N 帧（None=不限，保持旧行为）
    - diversity：按帧间像素差选 top-max_per_video 差异最大的帧（需 max_per_video）
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

    frame_images = _extract_frames(mat_dir, videos, fps, max_per_video, diversity)

    all_images = images + frame_images
    return [{"file": str(p.resolve()), "filename": p.name} for p in all_images[:max_count]]


def _extract_frames(
    mat_dir: Path,
    videos: list[Path],
    fps: float,
    max_per_video: int | None = None,
    diversity: bool = False,
) -> list[Path]:
    """对每个视频用 ffmpeg 抽帧到 .frames/<stem>/，返回所有抽出的 jpg 路径。

    max_per_video 给定时限制每视频贡献帧数；diversity=True 时按帧间差异选 top-k，
    否则取前 max_per_video 帧（保持时序）。
    """
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
            if not frames:
                continue
            if max_per_video is not None and len(frames) > max_per_video:
                if diversity:
                    frames = _select_diverse_frames(frames, top_k=max_per_video)
                else:
                    frames = frames[:max_per_video]
            all_frames.extend(frames)
            log.info("视频 %s 抽出 %d 帧", vid.name, len(frames))
        except subprocess.CalledProcessError as e:
            log.warning("视频 %s 抽帧失败 (exit %d): %s", vid.name, e.returncode,
                        (e.stderr or b"").decode("utf-8", errors="replace")[-200:])
        except subprocess.TimeoutExpired:
            log.warning("视频 %s 抽帧超时（>180s）", vid.name)
    return all_frames


def _select_diverse_frames(frames: list[Path], top_k: int) -> list[Path]:
    """从一组时序帧中选 top_k 帧，按相邻帧像素差（sum of abs diff）排序取差异最大者。

    - 计算每帧与前一帧的灰度差（首帧差视为 0）
    - 按差异度取 top_k，但**保持原始时间顺序**返回（避免乱序破坏叙事）
    - PIL/numpy 不可用或读图失败时回退到均匀采样（不崩）
    """
    if len(frames) <= top_k:
        return frames
    try:
        from PIL import Image
        import numpy as np

        diffs: list[tuple[float, Path]] = []
        prev_arr = None
        for fp in frames:
            img = np.asarray(Image.open(fp).convert("L").resize((64, 64)))
            if prev_arr is None:
                diffs.append((0.0, fp))
            else:
                d = float(np.abs(img.astype(int) - prev_arr.astype(int)).sum())
                diffs.append((d, fp))
            prev_arr = img

        top_set = {fp for _, fp in sorted(diffs, key=lambda x: x[0], reverse=True)[:top_k]}
        return [fp for fp in frames if fp in top_set]
    except Exception as e:  # noqa: BLE001 - 回退均匀采样，绝不阻断抽帧
        log.warning("多样性选帧失败 (%s)，回退均匀采样", e)
        step = max(1, len(frames) // top_k)
        return frames[::step][:top_k]
