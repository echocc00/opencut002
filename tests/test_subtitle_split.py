"""屏级字幕切分测试（v0.6.1）。

锁定 split_subtitle_adaptive 文本切分 + compute_screen_durations 的 hanzi 映射 +
边界校验（修 v0.5.4 audit 的 char_cursor 越界静默 + 造假均分 bug）。
"""
from __future__ import annotations

from src.utils.subtitle_split import (
    split_subtitle_adaptive,
    compute_screen_durations,
    compute_ideal_chars,
    _clean_chars_count,
    _is_hanzi,
)


class TestComputeIdealChars:
    def test_zero_duration_returns_midpoint(self):
        assert compute_ideal_chars(20, 0.0) == 11  # (8+14)//2

    def test_clamps_to_bounds(self):
        # 极快语速 -> 仍受 max_ideal 限制
        assert compute_ideal_chars(100, 1.0) == 14
        # 极慢语速 -> 仍受 min_ideal 限制
        assert compute_ideal_chars(2, 10.0) == 8

    def test_typical(self):
        # 20 字 / 10s = 2 字/s，* 1.5s = 3 字/屏 -> clamp 到 8
        assert compute_ideal_chars(20, 10.0) == 8


class TestCleanCharsCount:
    def test_strips_whitespace(self):
        assert _clean_chars_count("a b\tc\nd") == 4

    def test_keeps_punctuation(self):
        assert _clean_chars_count("你好，世界。") == 6


class TestSplitSubtitleAdaptive:
    def test_empty_returns_empty(self):
        assert split_subtitle_adaptive("") == []
        assert split_subtitle_adaptive("   ") == []

    def test_short_text_single_screen(self):
        text = "短文案"
        assert split_subtitle_adaptive(text, audio_duration=2.0) == [text]

    def test_long_text_splits_within_hard_max(self):
        text = "一" * 30  # 30 字无标点
        screens = split_subtitle_adaptive(text, audio_duration=10.0, hard_max=16)
        assert len(screens) >= 2
        for s in screens:
            assert _clean_chars_count(s) <= 16

    def test_splits_at_punctuation(self):
        text = "第一句话。第二句话。第三句话。第四句话。"  # 20 clean chars -> 必拆
        screens = split_subtitle_adaptive(text, audio_duration=6.0)
        # 标点处必断 -> 多屏
        assert len(screens) >= 2
        # 每屏 <= hard_max
        for s in screens:
            assert _clean_chars_count(s) <= 16
        # 汉字全部保留
        rejoined_hanzi = "".join(c for s in screens for c in s if "一" <= c <= "鿿")
        assert rejoined_hanzi == "".join(c for c in text if "一" <= c <= "鿿")

    def test_hard_max_never_exceeded(self):
        text = "这是一个比较长的句子用来测试硬切上限是否生效" * 3
        screens = split_subtitle_adaptive(text, audio_duration=20.0, hard_max=16)
        for s in screens:
            assert _clean_chars_count(s) <= 16, f"屏超 16 字: {s}"


class TestComputeScreenDurationsHanziMapping:
    """锁定 v0.6.1 修复：hanzi-only 时间戳（forced_align 输出）正确映射。"""

    def _make_hanzi_ts(self, text: str, per_char: float = 0.2):
        """造 hanzi-only 时间戳（段内相对，非均匀可选）。"""
        ts = []
        t = 0.0
        for c in text:
            if _is_hanzi(c):
                ts.append({"word": c, "start": round(t, 3), "end": round(t + per_char, 3)})
                t += per_char
        return ts

    def test_empty_screens(self):
        assert compute_screen_durations("x", 0.0, 1.0, [], []) == []

    def test_no_timestamps_even_split(self):
        screens = ["甲", "乙", "丙"]
        r = compute_screen_durations("甲乙丙", 0.0, 3.0, [], screens)
        assert len(r) == 3
        assert r[0]["start"] == 0.0
        # 均分 1s/屏
        assert abs(r[0]["duration"] - 1.0) < 0.01

    def test_hanzi_only_timestamps_mapped_correctly(self):
        text = "你好世界测试"  # 6 汉字
        ts = self._make_hanzi_ts(text, per_char=0.5)  # 共 3s
        screens = split_subtitle_adaptive(text, audio_duration=3.0, hard_max=4)
        r = compute_screen_durations(text, 0.0, 3.0, ts, screens)
        assert len(r) == len(screens)
        # 首屏起 0，末屏止 audio_duration，无间隙
        assert r[0]["start"] == 0.0
        total = sum(s["duration"] for s in r)
        assert abs(total - 3.0) < 0.02, f"总时长 {total} != 3.0（有间隙）"
        # 每屏时长 > 0
        for s in r:
            assert s["duration"] > 0

    def test_hanzi_count_mismatch_falls_back_even_split(self):
        """汉字数 != 时间戳数 -> 均分 + 不崩（修 char_cursor 越界静默 bug）。"""
        text = "你好世界"  # 4 汉字
        ts = [{"word": "你", "start": 0.0, "end": 0.2}]  # 只 1 个时间戳（不匹配）
        screens = ["你好", "世界"]
        r = compute_screen_durations(text, 0.0, 4.0, ts, screens)
        # 均分 fallback：每屏 2s
        assert len(r) == 2
        assert abs(r[0]["duration"] - 2.0) < 0.01

    def test_screens_cover_full_audio_contiguous(self):
        """屏边界连续，覆盖 [0, audio_duration]。"""
        text = "今天讲解一个重要的知识点帮助大家理解"
        ts = self._make_hanzi_ts(text, per_char=0.15)
        audio_dur = 0.15 * len([c for c in text if _is_hanzi(c)])
        screens = split_subtitle_adaptive(text, audio_duration=audio_dur)
        if len(screens) <= 1:
            return  # 单屏不测
        r = compute_screen_durations(text, 5.0, audio_dur, ts, screens)
        # 连续：每屏 start = 上一屏 start+duration（允许浮点误差）
        for i in range(1, len(r)):
            gap = abs(r[i]["start"] - (r[i - 1]["start"] + r[i - 1]["duration"]))
            assert gap < 0.02, f"屏 {i} 与前有间隙 {gap}"
        # 末屏止于 audio_start + audio_duration
        last_end = r[-1]["start"] + r[-1]["duration"]
        assert abs(last_end - (5.0 + audio_dur)) < 0.02

    def test_global_to_absolute_offset(self):
        """audio_start 偏移正确加到每屏。"""
        text = "你好世界"
        ts = self._make_hanzi_ts(text, per_char=0.5)
        screens = ["你好", "世界"]
        r = compute_screen_durations(text, 10.0, 2.0, ts, screens)
        assert r[0]["start"] == 10.0  # audio_start + 0
