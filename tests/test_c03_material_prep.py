"""C0.3 素材准备测试：图片收集 + 视频抽帧"""
from pathlib import Path
from unittest.mock import patch

from src.tools.material_prep import prepare_materials


def test_collects_jpg_jpeg_png_case_insensitive(tmp_path):
    (tmp_path / "img1.jpg").write_bytes(b"x")
    (tmp_path / "img2.PNG").write_bytes(b"x")
    (tmp_path / "img3.jpeg").write_bytes(b"x")
    (tmp_path / "readme.txt").write_bytes(b"x")
    (tmp_path / "sub").mkdir()
    materials = prepare_materials(tmp_path)
    names = [m["filename"] for m in materials]
    assert "img1.jpg" in names
    assert "img2.PNG" in names
    assert "img3.jpeg" in names
    assert "readme.txt" not in names
    assert "sub" not in names


def test_sorted_by_name(tmp_path):
    for n in ["c.jpg", "a.jpg", "b.jpg"]:
        (tmp_path / n).write_bytes(b"x")
    materials = prepare_materials(tmp_path)
    assert [m["filename"] for m in materials] == ["a.jpg", "b.jpg", "c.jpg"]


def test_max_count_limit(tmp_path):
    for i in range(8):
        (tmp_path / f"img{i}.jpg").write_bytes(b"x")
    materials = prepare_materials(tmp_path, max_count=3)
    assert len(materials) == 3


def test_empty_dir_returns_empty(tmp_path):
    assert prepare_materials(tmp_path) == []


def test_file_paths_are_absolute(tmp_path):
    (tmp_path / "img.jpg").write_bytes(b"x")
    materials = prepare_materials(tmp_path)
    assert Path(materials[0]["file"]).is_absolute()


def test_video_skipped_when_no_ffmpeg(tmp_path):
    """有视频但无 ffmpeg -> 跳过视频，仅返回图片"""
    (tmp_path / "img.jpg").write_bytes(b"x")
    (tmp_path / "clip.mp4").write_bytes(b"x")
    with patch("src.tools.material_prep.shutil.which", return_value=None):
        materials = prepare_materials(tmp_path)
    assert len(materials) == 1
    assert materials[0]["filename"] == "img.jpg"


def test_video_frame_extraction(tmp_path):
    """有视频且有 ffmpeg -> 调 ffmpeg 抽帧，抽出的帧加入列表（图片优先）"""
    (tmp_path / "img.jpg").write_bytes(b"x")
    (tmp_path / "clip.mp4").write_bytes(b"x")

    def fake_run(cmd, **kw):
        out_pattern = cmd[-1]
        out_dir = Path(out_pattern).parent
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "frame_001.jpg").write_bytes(b"x")
        (out_dir / "frame_002.jpg").write_bytes(b"x")
        return type("R", (), {"returncode": 0})()

    with patch("src.tools.material_prep.shutil.which", return_value="/fake/ffmpeg"), \
         patch("src.tools.material_prep.subprocess.run", side_effect=fake_run):
        materials = prepare_materials(tmp_path, max_count=10)
    names = [m["filename"] for m in materials]
    assert names[0] == "img.jpg"  # 图片优先
    assert "frame_001.jpg" in names
    assert "frame_002.jpg" in names
    assert len(materials) == 3


def test_video_extraction_failure_skipped(tmp_path):
    """ffmpeg 抽帧失败（非零退出）-> 跳过该视频，不阻断"""
    (tmp_path / "img.jpg").write_bytes(b"x")
    (tmp_path / "bad.mp4").write_bytes(b"x")

    def fake_run(cmd, **kw):
        import subprocess
        raise subprocess.CalledProcessError(1, cmd, stderr=b"invalid codec")

    with patch("src.tools.material_prep.shutil.which", return_value="/fake/ffmpeg"), \
         patch("src.tools.material_prep.subprocess.run", side_effect=fake_run):
        materials = prepare_materials(tmp_path, max_count=10)
    assert len(materials) == 1  # 只剩图片
    assert materials[0]["filename"] == "img.jpg"
