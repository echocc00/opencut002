"""自动构图（v0.6.2）- 横版素材智能裁 9:16，聚焦人脸。

opt-in: OPENCUT_AUTO_REFRAME=1。render_agent._stage_asset 链式调用：
get_masked_path -> get_reframed_path。material_analysis 见原图（更早跑，不调 _stage_asset）。

复用 face_masker.detect_faces 算人脸焦点；无人脸则图中。失败返原图（同 get_masked_path 模式）。
需 [face] extras（opencv，与 face_masker 共用）。
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from ..providers.provider_registry import ToolRuntime
from .face_masker import detect_faces

log = logging.getLogger(__name__)

# 运行时分类（v0.6.2）：纯本地 CPU（opencv 检测 + ffmpeg 裁剪）
RUNTIME: ToolRuntime = ToolRuntime.LOCAL

_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
_TARGET_RATIO = 9 / 16  # 竖版 9:16


def is_enabled() -> bool:
    return os.environ.get("OPENCUT_AUTO_REFRAME", "").strip().lower() in ("1", "true", "yes", "on")


def _compute_crop_box(w: int, h: int,
                      faces: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    """返回 (x, y, crop_w, crop_h) - 9:16 crop，人脸质心居中（无人脸图中）。

    横图（w/h > 9/16）：裁宽，crop_h=h, crop_w=h*9/16，按人脸 x 居中。
    竖图（w/h < 9/16）：裁高，crop_w=w, crop_h=w*16/9，垂直居中。
    恰好 9:16：整图（幂等）。
    """
    if w / h > _TARGET_RATIO:
        crop_h = h
        crop_w = int(h * _TARGET_RATIO)
    else:
        crop_w = w
        crop_h = int(w / _TARGET_RATIO)
    # 防御：不超原图
    crop_w = min(crop_w, w)
    crop_h = min(crop_h, h)

    if faces:
        cx = sum(x + fw // 2 for x, _, fw, _ in faces) // len(faces)
    else:
        cx = w // 2
    x = max(0, min(cx - crop_w // 2, w - crop_w))
    y = max(0, (h - crop_h) // 2)
    return (x, y, crop_w, crop_h)


def _reframe(src: Path, dst: Path) -> str:
    """ffmpeg crop 到 9:16（不缩放，render 的 objectFit:cover 负责缩放）。失败返原图。"""
    import cv2
    img = cv2.imread(str(src))
    if img is None:
        log.warning("auto_reframe: 读图失败 %s", src)
        return str(src)
    h, w = img.shape[:2]
    faces = detect_faces(str(src))
    x, y, cw, ch = _compute_crop_box(w, h, faces)
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", str(src),
         "-vf", f"crop={cw}:{ch}:{x}:{y}", "-frames:v", "1", str(dst)],
        capture_output=True, timeout=30,
    )
    if r.returncode != 0 or not dst.exists():
        log.warning("auto_reframe ffmpeg 失败 %s: %s", src.name, r.stderr.decode(errors="replace")[-200:])
        return str(src)
    return str(dst)


def get_reframed_path(src_path: str | Path) -> str:
    """返回 reframed 副本路径（按需创建+缓存）。

    - OPENCUT_AUTO_REFRAME 关 -> 返原图
    - 非图片 -> 返原图
    - 图片 -> <stem>.reframed.jpg（缓存；失败返原图）
    """
    if not is_enabled():
        return str(src_path)
    src = Path(src_path)
    if src.suffix.lower() not in _IMAGE_EXTS:
        return str(src_path)
    dst = src.parent / f"{src.stem}.reframed.jpg"
    if dst.exists():
        return str(dst)
    try:
        result = _reframe(src, dst)
        if result == str(dst):
            log.info("auto_reframe: %s -> %s", src.name, dst.name)
            return str(dst)
        return str(src_path)  # _reframe 内部失败已返原图
    except Exception as e:
        log.warning("auto_reframe 失败 %s, 用原图: %s", src.name, e)
        return str(src_path)
