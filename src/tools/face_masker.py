"""人脸遮盖工具 - opencv YuNet 检测 + 可爱贴纸 bake 进图片。

opt-in: OPENCUT_FACE_MASK=1 开启。render_agent._stage_asset 优先用 masked 副本。
material_analysis 用原图（描述准），render 用贴纸图。贴纸 bake 进图后随 Ken Burns
缩放/平移自然对齐人脸。非图片（音频）跳过。

模型: src/tools/models/yunet.onnx（YuNet，opencv_zoo）。缺失则回退 Haar cascade。
贴纸: src/tools/stickers/*.png（openmoji，CC-BY-SA 4.0 与 GPL-3.0 兼容）。
"""
from __future__ import annotations

import logging
import os
import random
from pathlib import Path

log = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_MODEL_PATH = _HERE / "models" / "yunet.onnx"
_STICKER_DIR = _HERE / "stickers"
_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}

_detector = None
_stickers: list[Path] | None = None


def is_enabled() -> bool:
    return os.environ.get("OPENCUT_FACE_MASK", "").strip().lower() in ("1", "true", "yes", "on")


def _load_detector():
    """YuNet 优先，Haar cascade 兜底。返回 (kind, model) 或 None。"""
    global _detector
    if _detector is not None:
        return _detector
    try:
        import cv2
        if _MODEL_PATH.exists():
            det = cv2.FaceDetectorYN.create(str(_MODEL_PATH), "", (320, 320), score_threshold=0.4)
            _detector = ("yunet", det)
            log.info("人脸检测: YuNet")
            return _detector
    except Exception:
        log.warning("YuNet 加载失败，回退 Haar cascade", exc_info=True)
    try:
        import cv2
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        _detector = ("haar", cascade)
        log.info("人脸检测: Haar cascade（兜底）")
        return _detector
    except Exception:
        log.error("人脸检测不可用（opencv 未装或模型缺失）")
        return None


def _load_stickers() -> list[Path]:
    global _stickers
    if _stickers is not None:
        return _stickers
    _stickers = sorted(_STICKER_DIR.glob("*.png")) if _STICKER_DIR.exists() else []
    if not _stickers:
        log.warning("无贴纸 PNG（%s），人脸遮盖退化为不遮盖", _STICKER_DIR)
    return _stickers


def detect_faces(image_path: str | Path) -> list[tuple[int, int, int, int]]:
    """返回 [(x, y, w, h), ...] 人脸框"""
    det = _load_detector()
    if det is None:
        return []
    import cv2
    img = cv2.imread(str(image_path))
    if img is None:
        return []
    h, w = img.shape[:2]
    kind, model = det
    if kind == "yunet":
        model.setInputSize((w, h))
        _, faces = model.detect(img)
        if faces is None:
            return []
        return [(int(f[0]), int(f[1]), int(f[2]), int(f[3])) for f in faces]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = model.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    return [(int(x), int(y), int(w), int(h)) for x, y, w, h in faces]


def mask_image(src_path: str | Path, dst_path: str | Path) -> str:
    """检测人脸 + 贴纸遮盖，写到 dst_path。无人脸/无贴纸则拷贝原图。"""
    import shutil
    from PIL import Image

    src_path, dst_path = Path(src_path), Path(dst_path)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    stickers = _load_stickers()
    faces = detect_faces(src_path)
    if not faces or not stickers:
        shutil.copy2(src_path, dst_path)
        return str(dst_path)

    img = Image.open(src_path).convert("RGBA")
    for (x, y, fw, fh) in faces:
        sticker_path = random.choice(stickers)
        # 贴纸放大到人脸 1.4 倍，居中覆盖人脸
        size = int(max(fw, fh) * 1.4)
        sticker = Image.open(sticker_path).convert("RGBA").resize((size, size), Image.LANCZOS)
        cx, cy = x + fw // 2, y + fh // 2
        img.alpha_composite(sticker, (cx - size // 2, cy - size // 2))
    img.convert("RGB").save(dst_path, "JPEG", quality=92)
    return str(dst_path)


def get_masked_path(src_path: str | Path) -> str:
    """返回 masked 副本路径（按需创建+缓存）。

    - OPENCUT_FACE_MASK 未开 -> 返回原图
    - 非图片（音频等）-> 返回原图
    - 图片 -> 同目录 <stem>.masked.jpg（缓存）
    """
    if not is_enabled():
        return str(src_path)
    src = Path(src_path)
    if src.suffix.lower() not in _IMAGE_EXTS:
        return str(src_path)
    dst = src.parent / f"{src.stem}.masked.jpg"
    if not dst.exists():
        try:
            mask_image(src, dst)
            log.info("人脸遮盖: %s -> %s", src.name, dst.name)
        except Exception:
            log.warning("人脸遮盖失败 %s，用原图", src.name, exc_info=True)
            return str(src_path)
    return str(dst)
