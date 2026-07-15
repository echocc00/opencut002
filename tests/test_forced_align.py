"""forced align 测试: chunking 逻辑 + fallback + env 开关（无需模型）"""
import os
import pytest


class TestChunkSubtitleLines:
    """RenderAgent._chunk_subtitle_lines 纯逻辑测试（无需模型）。"""

    def test_short_text_single_line(self):
        from src.agents.render_agent import RenderAgent
        words = [
            {"word": "你", "start": 0.0, "end": 0.2},
            {"word": "好", "start": 0.2, "end": 0.4},
        ]
        lines = RenderAgent._chunk_subtitle_lines(words, "你好")
        assert len(lines) == 1
        assert lines[0]["text"] == "你好"
        assert lines[0]["start"] == 0.0
        assert lines[0]["end"] == 0.4

    def test_break_at_punctuation(self):
        from src.agents.render_agent import RenderAgent
        # seg_words 只含汉字（标点不在 align 输出里），full_text 含标点
        words = [
            {"word": "你", "start": 0.0, "end": 0.2},
            {"word": "好", "start": 0.2, "end": 0.4},
            {"word": "世", "start": 0.5, "end": 0.7},
            {"word": "界", "start": 0.7, "end": 0.9},
        ]
        lines = RenderAgent._chunk_subtitle_lines(words, "你好，世界")
        assert len(lines) == 2
        assert lines[0]["text"] == "你好，"
        assert lines[0]["start"] == 0.0
        assert lines[0]["end"] == 0.4
        assert lines[1]["text"] == "世界"
        assert lines[1]["start"] == 0.5
        assert lines[1]["end"] == 0.9

    def test_hard_break_at_max_chars(self):
        from src.agents.render_agent import RenderAgent
        # 20 汉字无标点 -> 应在 16 字硬切
        text = "一二三四五六七八九十一二三四五六七八九十"
        words = [{"word": c, "start": i * 0.1, "end": (i + 1) * 0.1}
                 for i, c in enumerate(text)]
        lines = RenderAgent._chunk_subtitle_lines(words, text, max_chars=16)
        assert len(lines) >= 2
        for line in lines:
            assert len(line["text"]) <= 16

    def test_empty_words(self):
        from src.agents.render_agent import RenderAgent
        assert RenderAgent._chunk_subtitle_lines([], "你好") == []
        assert RenderAgent._chunk_subtitle_lines([{"word": "你", "start": 0, "end": 1}], "") == []

    def test_char_count_mismatch_fallback_even_split(self):
        """汉字数与 seg_words 不匹配时回退均分。"""
        from src.agents.render_agent import RenderAgent
        words = [{"word": "你", "start": 0.0, "end": 0.4}]  # 只有 1 个，但 text 有 2 汉字
        lines = RenderAgent._chunk_subtitle_lines(words, "你好")
        assert len(lines) >= 1
        # 均分：line 在 [0, 0.4] 内
        assert lines[0]["start"] >= 0.0
        assert lines[0]["end"] <= 0.4 + 0.01


class TestForcedAlignFallback:
    """align_chars 在依赖缺失/模型加载失败时返回 None。"""

    def test_returns_none_when_deps_missing(self, monkeypatch):
        from src.tools import forced_align
        monkeypatch.setattr(forced_align, "_is_available", lambda: False)
        assert forced_align.align_chars("fake.mp3", "测试") is None

    def test_returns_none_when_model_load_fails(self, monkeypatch):
        from src.tools import forced_align
        monkeypatch.setattr(forced_align, "_is_available", lambda: True)
        monkeypatch.setattr(forced_align, "_load_model", lambda: False)
        assert forced_align.align_chars("fake.mp3", "测试") is None

    def test_filter_chars_keeps_only_hanzi(self):
        from src.tools.forced_align import _filter_chars
        assert _filter_chars("你好，世界！123abc") == ["你", "好", "世", "界"]
        assert _filter_chars("，。！123") == []
        assert _filter_chars("") == []


class TestEnvSwitches:
    """OPENCUT_TRIM_SILENCE / OPENCUT_FORCED_ALIGN env 开关。"""

    @pytest.mark.parametrize("env_name,func_name", [
        ("OPENCUT_TRIM_SILENCE", "_trim_silence_enabled"),
        ("OPENCUT_FORCED_ALIGN", "_forced_align_enabled"),
    ])
    def test_disabled_by_default(self, env_name, func_name, monkeypatch):
        monkeypatch.delenv(env_name, raising=False)
        from src.agents import tts_agent
        assert getattr(tts_agent, func_name)() is False

    @pytest.mark.parametrize("env_name,func_name", [
        ("OPENCUT_TRIM_SILENCE", "_trim_silence_enabled"),
        ("OPENCUT_FORCED_ALIGN", "_forced_align_enabled"),
    ])
    def test_enabled_when_set(self, env_name, func_name, monkeypatch):
        monkeypatch.setenv(env_name, "1")
        from src.agents import tts_agent
        assert getattr(tts_agent, func_name)() is True

    @pytest.mark.parametrize("env_name,func_name", [
        ("OPENCUT_TRIM_SILENCE", "_trim_silence_enabled"),
        ("OPENCUT_FORCED_ALIGN", "_forced_align_enabled"),
    ])
    def test_truthy_values(self, env_name, func_name, monkeypatch):
        from src.agents import tts_agent
        for val in ("1", "true", "yes", "on", "TRUE"):
            monkeypatch.setenv(env_name, val)
            assert getattr(tts_agent, func_name)() is True, f"{val} should be truthy"
