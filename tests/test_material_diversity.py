"""素材多样性抽帧测试（v0.6.4，opt-in OPENCUT_MATERIAL_DIVERSITY）。

默认 diversity=False / max_per_video=None 时行为与 v0.6.3 完全一致。
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from src.tools.material_prep import (
    DIVERSITY_MAX_PER_VIDEO,
    _select_diverse_frames,
    diversity_enabled,
    prepare_materials,
)

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402


def _make_frames(dirpath: Path, n: int, gray_step: int = 40) -> list[Path]:
    dirpath.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(n):
        v = min(255, i * gray_step)
        p = dirpath / f"frame_{i:03d}.jpg"
        Image.new("RGB", (64, 64), color=(v, v, v)).save(p)
        paths.append(p)
    return paths


class TestDiversityDefault:
    def test_default_off(self, monkeypatch):
        monkeypatch.delenv("OPENCUT_MATERIAL_DIVERSITY", raising=False)
        assert diversity_enabled() is False

    def test_env_on(self, monkeypatch):
        monkeypatch.setenv("OPENCUT_MATERIAL_DIVERSITY", "1")
        assert diversity_enabled() is True

    def test_images_unchanged_default(self, tmp_path):
        """无视频、diversity 默认关：图片收录行为不变。"""
        for i in range(3):
            (tmp_path / f"img{i}.jpg").write_bytes(b"x")
        materials = prepare_materials(tmp_path)
        assert len(materials) == 3
        assert all(m["filename"].startswith("img") for m in materials)

    def test_max_count_default_still_5(self, tmp_path):
        """默认 max_count=5 保持不变（fork 改 30 的行为变更不采纳）。"""
        for i in range(8):
            (tmp_path / f"img{i}.jpg").write_bytes(b"x")
        assert len(prepare_materials(tmp_path)) == 5


class TestMaxPerVideo:
    def _fake_run_factory(self, n_frames: int):
        def fake_run(cmd, **kw):
            out_dir = Path(cmd[-1]).parent
            out_dir.mkdir(parents=True, exist_ok=True)
            for i in range(1, n_frames + 1):
                (out_dir / f"frame_{i:03d}.jpg").write_bytes(b"x")
            return type("R", (), {"returncode": 0})()
        return fake_run

    def test_max_per_video_none_unlimited(self, tmp_path):
        """max_per_video=None（默认）：不裁剪，全收。"""
        (tmp_path / "clip.mp4").write_bytes(b"x")
        with patch("src.tools.material_prep.shutil.which", return_value="/fake/ffmpeg"), \
             patch("src.tools.material_prep.subprocess.run", side_effect=self._fake_run_factory(10)):
            materials = prepare_materials(tmp_path, max_count=100)
        assert len(materials) == 10

    def test_max_per_video_caps(self, tmp_path):
        (tmp_path / "clip.mp4").write_bytes(b"x")
        with patch("src.tools.material_prep.shutil.which", return_value="/fake/ffmpeg"), \
             patch("src.tools.material_prep.subprocess.run", side_effect=self._fake_run_factory(10)):
            materials = prepare_materials(tmp_path, max_per_video=2, max_count=100)
        assert len(materials) == 2

    def test_diversity_flag_path(self, tmp_path):
        """diversity=True + max_per_video 走 _select_diverse_frames（真实图）。"""
        (tmp_path / "clip.mp4").write_bytes(b"x")
        frames_dir = tmp_path / ".frames" / "clip"

        def fake_run(cmd, **kw):
            frames_dir.mkdir(parents=True, exist_ok=True)
            for i in range(1, 7):
                v = i * 40
                Image.new("RGB", (64, 64), color=(v, v, v)).save(frames_dir / f"frame_{i:03d}.jpg")
            return type("R", (), {"returncode": 0})()

        with patch("src.tools.material_prep.shutil.which", return_value="/fake/ffmpeg"), \
             patch("src.tools.material_prep.subprocess.run", side_effect=fake_run):
            materials = prepare_materials(tmp_path, max_per_video=3, diversity=True, max_count=100)
        assert len(materials) == 3


class TestSelectDiverseFrames:
    def test_keeps_time_order(self, tmp_path):
        paths = _make_frames(tmp_path / "f", 5)
        selected = _select_diverse_frames(paths, top_k=3)
        idx = [paths.index(p) for p in selected]
        assert idx == sorted(idx)
        assert len(selected) == 3

    def test_fewer_than_k_returns_all(self, tmp_path):
        paths = _make_frames(tmp_path / "f", 2)
        assert _select_diverse_frames(paths, top_k=5) == paths

    def test_pil_numpy_unavailable_fallback(self, tmp_path):
        paths = _make_frames(tmp_path / "f", 6)
        with patch.dict(sys.modules, {"PIL.Image": None, "numpy": None}):
            selected = _select_diverse_frames(paths, top_k=3)
        assert len(selected) == 3

    def test_constant_value(self):
        assert DIVERSITY_MAX_PER_VIDEO == 3


class TestExtractFramesEdge:
    def test_no_ffmpeg_skips(self, tmp_path):
        """无 ffmpeg：跳过视频抽帧，不崩，返回空帧列表。"""
        from src.tools.material_prep import _extract_frames
        (tmp_path / "clip.mp4").write_bytes(b"x")
        with patch("src.tools.material_prep.shutil.which", return_value=None):
            assert _extract_frames(tmp_path, [tmp_path / "clip.mp4"], 0.2) == []

    def test_ffmpeg_failure_skips_video(self, tmp_path):
        """单视频抽帧 CalledProcessError：跳过该视频，不阻断。"""
        import subprocess as _sp
        from src.tools.material_prep import _extract_frames
        vid = tmp_path / "clip.mp4"
        vid.write_bytes(b"x")
        err = _sp.CalledProcessError(1, "ffmpeg", stderr=b"boom")
        with patch("src.tools.material_prep.shutil.which", return_value="/fake/ffmpeg"), \
             patch("src.tools.material_prep.subprocess.run", side_effect=err):
            assert _extract_frames(tmp_path, [vid], 0.2) == []

    def test_no_pil_fallback_in_prepare(self, tmp_path):
        """diversity=True 但 PIL 不可用：_select_diverse_frames 回退均匀采样，仍出帧。"""
        (tmp_path / "clip.mp4").write_bytes(b"x")
        frames_dir = tmp_path / ".frames" / "clip"

        def fake_run(cmd, **kw):
            frames_dir.mkdir(parents=True, exist_ok=True)
            for i in range(1, 7):
                (frames_dir / f"frame_{i:03d}.jpg").write_bytes(b"x")
            return type("R", (), {"returncode": 0})()

        with patch("src.tools.material_prep.shutil.which", return_value="/fake/ffmpeg"), \
             patch("src.tools.material_prep.subprocess.run", side_effect=fake_run), \
             patch.dict(sys.modules, {"PIL.Image": None, "numpy": None}):
            materials = prepare_materials(tmp_path, max_per_video=3, diversity=True, max_count=100)
        assert len(materials) == 3
