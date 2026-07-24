"""clip_montage_scorer 故事板蒙太奇质量评分器测试（v0.6.4）。"""
from __future__ import annotations

from src.quality.clip_montage_scorer import ClipMontageScore, score_clip_storyboard


def _video_seg(source_id: str, file: str, duration: float, time_start: float,
               actual: float | None = None) -> dict:
    return {
        "asset_type": "video",
        "clip": {"source_id": source_id, "file": file, "duration": duration},
        "actual_duration": actual if actual is not None else duration,
        "time_start": time_start,
    }


class TestEmptyAndBasic:
    def test_empty_storyboard_critical(self):
        s = score_clip_storyboard([])
        assert s.passed is False
        assert s.risk_level == "critical"
        assert s.total_score == 100.0

    def test_returns_score_dataclass(self):
        s = score_clip_storyboard([])
        assert isinstance(s, ClipMontageScore)

    def test_healthy_storyboard_passes(self, tmp_path):
        f = tmp_path / "c.mp4"
        f.write_bytes(b"x")
        segs = [
            _video_seg(f"src{i}", str(f), 5.0, i * 5.0)
            for i in range(6)
        ]
        s = score_clip_storyboard(segs, min_unique_sources=5)
        assert s.passed is True
        assert s.metrics["unique_sources"] == 6
        assert s.metrics["timeline_discontinuities"] == 0


class TestRiskDimensions:
    def test_low_video_ratio_flagged(self, tmp_path):
        f = tmp_path / "c.mp4"
        f.write_bytes(b"x")
        # 5 个图像段只有 1 个视频 -> video_ratio 0.2 < 0.8
        segs = [_video_seg("s0", str(f), 5.0, 0.0)]
        segs += [{"asset_type": "image", "image": "x.jpg", "actual_duration": 3.0,
                  "time_start": 5.0 + i * 3.0} for i in range(4)]
        s = score_clip_storyboard(segs)
        assert not s.passed
        assert any("video ratio" in i for i in s.issues)

    def test_source_reuse_exceeds(self, tmp_path):
        f = tmp_path / "c.mp4"
        f.write_bytes(b"x")
        # 同一个源用 5 次 -> max_reuse 5 > 2
        segs = [_video_seg("same", str(f), 5.0, i * 5.0) for i in range(5)]
        s = score_clip_storyboard(segs, min_unique_sources=1)
        assert not s.passed
        assert any("source reuse" in i for i in s.issues)

    def test_consecutive_same_source(self, tmp_path):
        f = tmp_path / "c.mp4"
        f.write_bytes(b"x")
        segs = [_video_seg("a", str(f), 5.0, 0.0), _video_seg("a", str(f), 5.0, 5.0)]
        segs += [_video_seg(f"u{i}", str(f), 5.0, 10.0 + i * 5.0) for i in range(4)]
        s = score_clip_storyboard(segs, min_unique_sources=1, max_source_reuse=5)
        assert any("consecutive" in i for i in s.issues)

    def test_missing_clip_file(self, tmp_path):
        good = tmp_path / "ok.mp4"
        good.write_bytes(b"x")
        segs = [_video_seg(f"s{i}", str(good), 5.0, i * 5.0) for i in range(5)]
        segs.append(_video_seg("bad", "/nonexistent/nope.mp4", 5.0, 25.0))
        s = score_clip_storyboard(segs, min_unique_sources=1)
        assert not s.passed
        assert any("missing clip" in i for i in s.issues)

    def test_short_clip(self, tmp_path):
        f = tmp_path / "c.mp4"
        f.write_bytes(b"x")
        # clip duration 2s 但段需要 5s -> short
        segs = [_video_seg("s0", str(f), 2.0, 0.0, actual=5.0)]
        segs += [_video_seg(f"s{i}", str(f), 5.0, 5.0 + (i - 1) * 5.0) for i in range(1, 6)]
        s = score_clip_storyboard(segs, min_unique_sources=1, max_source_reuse=10)
        assert any("short clips" in i for i in s.issues)

    def test_timeline_discontinuity(self, tmp_path):
        f = tmp_path / "c.mp4"
        f.write_bytes(b"x")
        segs = [
            _video_seg("s0", str(f), 5.0, 0.0),
            _video_seg("s1", str(f), 5.0, 8.0),   # 应在 5.0，跳了 -> 不连续
            _video_seg("s2", str(f), 5.0, 13.0),
            _video_seg("s3", str(f), 5.0, 18.0),
            _video_seg("s4", str(f), 5.0, 23.0),
        ]
        s = score_clip_storyboard(segs, min_unique_sources=1, max_source_reuse=10)
        assert any("discontinuities" in i for i in s.issues)


class TestFaceMaskGate:
    def test_face_mask_below_threshold_fails(self, tmp_path):
        f = tmp_path / "c.mp4"
        f.write_bytes(b"x")
        segs = [_video_seg(f"s{i}", str(f), 5.0, i * 5.0) for i in range(6)]
        # 有 file 的段才算 masked；这里全有 -> coverage 1.0，设阈值更高无意义
        # 用无 file 段拉低覆盖率
        segs.append({"asset_type": "video", "clip": {"source_id": "x"}, "time_start": 30.0})
        s = score_clip_storyboard(segs, min_unique_sources=1, min_face_mask_ratio=1.0)
        assert any("face mask coverage" in i for i in s.issues)

    def test_face_mask_gate_off_by_default(self, tmp_path):
        f = tmp_path / "c.mp4"
        f.write_bytes(b"x")
        segs = [_video_seg(f"s{i}", str(f), 5.0, i * 5.0) for i in range(6)]
        s = score_clip_storyboard(segs, min_unique_sources=5)  # min_face_mask_ratio=0
        assert not any("face mask" in i for i in s.issues)


class TestRiskLevel:
    def test_risk_level_bands(self):
        # 空段 -> critical（100）
        assert score_clip_storyboard([]).risk_level == "critical"

    def test_blank_fallback_flagged(self):
        """视觉段既无 clip 也无 image -> blank_fallback。"""
        segs = [
            {"asset_type": "image", "actual_duration": 3.0, "time_start": 0.0},  # 无 image
            {"asset_type": "image", "image": "a.jpg", "actual_duration": 3.0, "time_start": 3.0},
        ]
        s = score_clip_storyboard(segs, min_video_ratio=0.0, min_unique_sources=0)
        assert any("blank fallbacks" in i for i in s.issues)
