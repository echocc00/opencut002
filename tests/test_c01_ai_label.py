"""C0.1 AI 生成标识开关测试：渲染数据字段 + env 开关"""
import os
from unittest.mock import patch

from src.agents.render_agent import _ai_label_enabled
from src.tools.remotion_renderer import RemotionRenderer


def test_build_render_data_ai_label_defaults_false():
    data = RemotionRenderer.build_render_data(
        title="t", title_duration=2.0, segments=[], voice_path="",
    )
    assert data["aiLabel"] is False


def test_build_render_data_ai_label_true():
    data = RemotionRenderer.build_render_data(
        title="t", title_duration=2.0, segments=[], voice_path="", ai_label=True,
    )
    assert data["aiLabel"] is True


def test_ai_label_enabled_reads_env(monkeypatch):
    monkeypatch.delenv("OPENCUT_AI_LABEL", raising=False)
    assert _ai_label_enabled() is False

    monkeypatch.setenv("OPENCUT_AI_LABEL", "1")
    assert _ai_label_enabled() is True

    monkeypatch.setenv("OPENCUT_AI_LABEL", "true")
    assert _ai_label_enabled() is True

    monkeypatch.setenv("OPENCUT_AI_LABEL", "yes")
    assert _ai_label_enabled() is True

    monkeypatch.setenv("OPENCUT_AI_LABEL", "0")
    assert _ai_label_enabled() is False

    monkeypatch.setenv("OPENCUT_AI_LABEL", "")
    assert _ai_label_enabled() is False
