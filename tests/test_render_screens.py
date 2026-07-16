"""屏级 segment 构造测试（v0.6.1）- render_agent._build_screen_segments。"""
from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.agents.render_agent import RenderAgent


@pytest.fixture
def agent():
    return RenderAgent(
        skill_loader=Mock(), provider_selector=Mock(), decision_logger=Mock(),
    )


def _hanzi_ts(text, per_char=0.2, offset=0.0):
    """造 hanzi-only 全局绝对时间戳（forced_align 输出形状）。"""
    ts = []
    t = offset
    for c in text:
        if "一" <= c <= "鿿":
            ts.append({"word": c, "start": round(t, 3), "end": round(t + per_char, 3)})
            t += per_char
    return ts


class TestBuildScreenSegments:
    def test_single_screen_returns_none(self, agent):
        """短文本单屏 -> None（走段级 fallback）。"""
        pt = {"index": 0, "start": 0.0, "duration": 1.0, "text": "短"}
        r = agent._build_screen_segments(pt, "img.jpg", "", [], set(), _hanzi_ts("短"), "crossfade")
        assert r is None

    def test_multi_screen_returns_segments(self, agent):
        text = "今天我们来讲解一个非常重要的知识点它可以帮助大家理解"
        pt = {"index": 0, "start": 0.0, "duration": 5.0, "text": text}
        r = agent._build_screen_segments(pt, "img.jpg", "", [], set(), _hanzi_ts(text, per_char=0.1), "crossfade")
        assert r is not None
        assert len(r) >= 2
        # 所有屏共享同一段 index
        for seg in r:
            assert seg["index"] == 0
            assert seg["screens_total"] == len(r)
            assert seg["subtitle"]  # 有字幕
            assert seg["actual_duration"] > 0

    def test_screen_index_and_transition(self, agent):
        text = "今天我们来讲解一个非常重要的知识点它可以帮助大家理解"
        pt = {"index": 0, "start": 0.0, "duration": 5.0, "text": text}
        r = agent._build_screen_segments(pt, "img.jpg", "", [], set(), _hanzi_ts(text, per_char=0.1), "slide")
        assert r is not None
        for i, seg in enumerate(r):
            assert seg["screen_index"] == i
            assert seg["transition"] == "slide" if i == 0 else "fade"

    def test_image_candidate_rotation(self, agent):
        """4 层兜底 + 屏间轮换：match -> sb -> materials。"""
        text = "今天我们来讲解一个非常重要的知识点它可以帮助大家理解"
        pt = {"index": 0, "start": 0.0, "duration": 5.0, "text": text}
        mats = ["/m/m1.jpg", "/m/m2.jpg", "/m/m3.jpg"]
        r = agent._build_screen_segments(pt, "/match/a.jpg", "/sb/b.jpg", mats, set(),
                                         _hanzi_ts(text, per_char=0.1), "crossfade")
        assert r is not None
        # 候选列表：[match, sb, m1, m2, m3]，屏按 scr_idx % len 轮换
        cands = ["/match/a.jpg", "/sb/b.jpg", "/m/m1.jpg", "/m/m2.jpg", "/m/m3.jpg"]
        for i, seg in enumerate(r):
            assert seg["image"] == cands[i % len(cands)]

    def test_text_card_when_no_candidates(self, agent):
        text = "今天我们来讲解一个非常重要的知识点它可以帮助大家理解"
        pt = {"index": 2, "start": 0.0, "duration": 5.0, "text": text}
        # 无候选 + 段在 text_cards -> text_card=True
        r = agent._build_screen_segments(pt, "", "", [], {2}, _hanzi_ts(text, per_char=0.1), "crossfade")
        assert r is not None
        for seg in r:
            assert seg["text_card"] is True
            assert seg["image"] == ""

    def test_screen_timing_from_real_timestamps(self, agent):
        """屏时长由真实时间戳驱动，覆盖 [start, start+duration]。"""
        text = "今天我们来讲解一个非常重要的知识点它可以帮助大家理解"  # 24 汉字
        per_char = 0.2
        dur = per_char * 24  # 4.8s
        pt = {"index": 0, "start": 10.0, "duration": dur, "text": text}
        r = agent._build_screen_segments(pt, "img.jpg", "", [], set(),
                                         _hanzi_ts(text, per_char=per_char, offset=10.0), "crossfade")
        assert r is not None
        # 首屏起 10.0，末屏止 10.0+dur
        assert r[0]["time_start"] == 10.0
        last_end = r[-1]["time_start"] + r[-1]["actual_duration"]
        assert abs(last_end - (10.0 + dur)) < 0.05
        # 屏间连续
        for i in range(1, len(r)):
            assert abs(r[i]["time_start"] - (r[i - 1]["time_start"] + r[i - 1]["actual_duration"])) < 0.02

    def test_global_timestamps_filtered_by_time_range(self, agent):
        """全局 word_timestamps 按时间段过滤（兼容混合数组）。"""
        text = "今天我们来讲解一个非常重要的知识点"  # 16 汉字 -> 必拆多屏
        # 全局数组里混了别的段的时间戳（offset 不同）
        other_ts = _hanzi_ts("其他段落不参与本段", per_char=0.2, offset=100.0)
        own_ts = _hanzi_ts(text, per_char=0.2, offset=5.0)
        all_ts = other_ts + own_ts  # 混合
        pt = {"index": 0, "start": 5.0, "duration": 16 * 0.2, "text": text}
        r = agent._build_screen_segments(pt, "img.jpg", "", [], set(), all_ts, "crossfade")
        # 应只用自己的时间戳（5.0~8.2 段），不被 other_ts (100+) 污染
        assert r is not None
        assert len(r) >= 2
        # 首屏起 5.0，末屏止 ~5.0+dur（不被 100+ 污染）
        assert r[0]["time_start"] == 5.0
        last_end = r[-1]["time_start"] + r[-1]["actual_duration"]
        assert last_end < 50.0  # 没被 other_ts (100+) 拉跑偏
