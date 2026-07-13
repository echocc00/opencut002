"""C1.2 人脸遮盖测试：opt-in 逻辑 + 非图片跳过 + 无人脸拷贝 + 检测器加载

真实人脸检测由 opencv YuNet 保证（库自带测试），这里测管道逻辑。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.tools.face_masker import (detect_faces, get_masked_path, is_enabled, mask_image,
                                   _load_detector, _load_stickers)


def test_is_enabled_respects_env(monkeypatch):
    monkeypatch.delenv("OPENCUT_FACE_MASK", raising=False)
    assert is_enabled() is False
    monkeypatch.setenv("OPENCUT_FACE_MASK", "1")
    assert is_enabled() is True
    monkeypatch.setenv("OPENCUT_FACE_MASK", "0")
    assert is_enabled() is False


def test_get_masked_path_disabled_returns_original(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENCUT_FACE_MASK", raising=False)
    img = tmp_path / "a.jpg"
    img.write_bytes(b"x")
    assert get_masked_path(img) == str(img)


def test_get_masked_path_skips_non_image(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENCUT_FACE_MASK", "1")
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"x")
    assert get_masked_path(audio) == str(audio)  # 音频不遮盖


def test_get_masked_path_creates_masked_copy(monkeypatch, tmp_path):
    """开启 + 图片 -> 产出 .masked.jpg 副本"""
    monkeypatch.setenv("OPENCUT_FACE_MASK", "1")
    # 重置单例（避免跨测试污染）
    import src.tools.face_masker as fm
    fm._detector = None
    fm._stickers = None
    img = tmp_path / "photo.jpg"
    _make_test_image(img)  # 无人脸的纯色图
    result = get_masked_path(img)
    assert result != str(img)
    assert Path(result).exists()
    assert ".masked" in Path(result).name
    # 缓存：第二次不重建（mtime 不变）
    mtime = Path(result).stat().st_mtime
    get_masked_path(img)
    assert Path(result).stat().st_mtime == mtime


def test_mask_image_no_face_copies(monkeypatch, tmp_path):
    """无人脸 -> dst 是原图拷贝（尺寸一致）"""
    import src.tools.face_masker as fm
    fm._detector = None
    src = tmp_path / "src.jpg"
    _make_test_image(src)
    dst = tmp_path / "out.jpg"
    mask_image(src, dst)
    assert dst.exists()
    # 尺寸一致（无人脸未改）
    from PIL import Image
    assert Image.open(src).size == Image.open(dst).size


def test_detector_loads():
    """opencv + YuNet 模型可用（或 Haar 兜底）"""
    import src.tools.face_masker as fm
    fm._detector = None
    det = _load_detector()
    assert det is not None  # opencv 装了，至少 Haar 兜底
    assert det[0] in ("yunet", "haar")


def test_stickers_available():
    """贴纸 PNG 存在"""
    stickers = _load_stickers()
    assert len(stickers) >= 1, "应有贴纸 PNG（src/tools/stickers/）"


def test_detect_faces_no_face_returns_empty(tmp_path):
    """纯色图无人脸 -> []"""
    import src.tools.face_masker as fm
    fm._detector = None
    img = tmp_path / "blank.jpg"
    _make_test_image(img)
    faces = detect_faces(img)
    assert faces == []


def _make_test_image(path: Path) -> None:
    """生成一张纯色无脸 jpg"""
    from PIL import Image
    Image.new("RGB", (200, 200), (100, 150, 200)).save(path, "JPEG")
