"""auto_reframe 测试（v0.6.2）。"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.tools.auto_reframe import (
    is_enabled, _compute_crop_box, get_reframed_path, RUNTIME,
)
from src.providers.provider_registry import ToolRuntime


class TestIsEnabled:
    def test_default_off(self, monkeypatch):
        monkeypatch.delenv("OPENCUT_AUTO_REFRAME", raising=False)
        assert is_enabled() is False

    def test_on(self, monkeypatch):
        monkeypatch.setenv("OPENCUT_AUTO_REFRAME", "1")
        assert is_enabled() is True


class TestRuntime:
    def test_runtime_local(self):
        assert RUNTIME == ToolRuntime.LOCAL


class TestComputeCropBox:
    def test_horizontal_centered_no_faces(self):
        """1920x1080 横图 -> 9:16 竖裁，居中。"""
        x, y, cw, ch = _compute_crop_box(1920, 1080, [])
        assert cw == 607  # 1080 * 9/16 = 607.5 -> 607
        assert ch == 1080
        assert y == 0
        # 居中：x = 960 - 303 = 657
        assert x == 657

    def test_face_focus_shifts_left(self):
        """人脸在左侧 -> crop 左移（x clamp 到 0）。"""
        faces = [(100, 100, 200, 200)]  # 质心 x = 200
        x, y, cw, ch = _compute_crop_box(1920, 1080, faces)
        assert cw == 607
        # 质心 200 - 303 = -103 -> clamp 0
        assert x == 0

    def test_face_focus_shifts_right(self):
        """人脸在右侧 -> crop 右移（clamp 不超界）。"""
        faces = [(1700, 100, 200, 200)]  # 质心 x = 1800
        x, y, cw, ch = _compute_crop_box(1920, 1080, faces)
        assert x == 1920 - 607  # clamp 到右边界 = 1313

    def test_idempotent_on_9_16(self):
        """恰好 9:16 -> 整图（幂等）。"""
        x, y, cw, ch = _compute_crop_box(1080, 1920, [])
        assert cw == 1080
        assert ch == 1920
        assert x == 0
        assert y == 0

    def test_vertical_taller_than_9_16(self):
        """比 9:16 更高 -> 裁高，垂直居中。"""
        # 1000x2000，w/h=0.5 < 0.5625
        x, y, cw, ch = _compute_crop_box(1000, 2000, [])
        assert cw == 1000
        assert ch == 1777  # int(1000 / 0.5625) = int(1777.7) = 1777
        assert x == 0
        assert y == (2000 - 1777) // 2  # 垂直居中

    def test_multiple_faces_centroid(self):
        """多人脸取质心。"""
        faces = [(100, 0, 200, 200), (1500, 0, 200, 200)]  # 质心 = (200 + 1600)/2 = 900
        x, y, cw, ch = _compute_crop_box(1920, 1080, faces)
        # 质心 900 - 303 = 597
        assert x == 597


class TestGetReframedPath:
    def test_disabled_returns_original(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPENCUT_AUTO_REFRAME", raising=False)
        p = tmp_path / "x.jpg"
        p.write_bytes(b"img")
        assert get_reframed_path(str(p)) == str(p)

    def test_non_image_returns_original(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENCUT_AUTO_REFRAME", "1")
        p = tmp_path / "voice.mp3"
        p.write_bytes(b"audio")
        assert get_reframed_path(str(p)) == str(p)

    def test_failure_returns_original(self, tmp_path, monkeypatch):
        """_reframe 失败（无 cv2/ffmpeg）-> 返原图。"""
        monkeypatch.setenv("OPENCUT_AUTO_REFRAME", "1")
        p = tmp_path / "x.jpg"
        p.write_bytes(b"img")
        with patch("src.tools.auto_reframe._reframe", side_effect=RuntimeError("boom")):
            assert get_reframed_path(str(p)) == str(p)
        # 不留 reframed 文件
        assert not (tmp_path / "x.reframed.jpg").exists()

    def test_caches_reframed(self, tmp_path, monkeypatch):
        """第二次调用用缓存（不重跑 _reframe）。"""
        monkeypatch.setenv("OPENCUT_AUTO_REFRAME", "1")
        p = tmp_path / "x.jpg"
        p.write_bytes(b"img")
        dst = tmp_path / "x.reframed.jpg"
        dst.write_bytes(b"reframed")  # 预置缓存

        called = []
        def fake_reframe(src, d):
            called.append(1)
            return str(d)
        with patch("src.tools.auto_reframe._reframe", side_effect=fake_reframe):
            assert get_reframed_path(str(p)) == str(dst)
        assert called == []  # 缓存命中，没调 _reframe


class TestReframeIntegration:
    """ffmpeg + cv2 集成（缺依赖跳过）。"""

    @pytest.fixture
    def _need_deps(self):
        try:
            import cv2  # noqa: F401
        except ImportError:
            pytest.skip("opencv 未装（[face] extras）")
        import shutil
        if not shutil.which("ffmpeg"):
            pytest.skip("ffmpeg 未装")

    def test_reframe_produces_9_16(self, _need_deps, tmp_path, monkeypatch):
        """横图 -> reframed 输出是 9:16 比例。"""
        import cv2
        import subprocess
        monkeypatch.setenv("OPENCUT_AUTO_REFRAME", "1")
        # 造 1920x1080 纯色图
        src = tmp_path / "src.jpg"
        img = _new_color_img(1920, 1080)
        cv2.imwrite(str(src), img)
        dst = tmp_path / "src.reframed.jpg"
        from src.tools.auto_reframe import _reframe
        result = _reframe(Path(src), Path(dst))
        assert result == str(dst)
        assert dst.exists()
        # 输出应是 9:16（约 607x1080）
        out = cv2.imread(str(dst))
        oh, ow = out.shape[:2]
        assert abs(ow / oh - 9 / 16) < 0.05, f"输出 {ow}x{oh} 非 9:16"


def _new_color_img(w, h):
    """造一张纯色 numpy 图（避免文件依赖）。"""
    import numpy as np
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:] = (123, 45, 67)  # BGR
    return img
