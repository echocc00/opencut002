"""C3 素材分层兜底测试：ImageMatchingAgent 分层决策（第1层复用/第2层文字卡/第3层生图）"""
from __future__ import annotations

import pytest
from unittest.mock import patch

from src.agents.image_matching_agent import ImageMatchingAgent
from src.orchestrator.state import ProjectState


def _state_with(paragraphs, images):
    state = ProjectState(project_id="test", domain="education")
    state.get_stage("material_analysis").output_data = {"images": images}
    state.get_stage("copywriting").output_data = {"paragraphs": paragraphs}
    return state


@pytest.mark.asyncio
async def test_strong_match_uses_matched_no_text_card(monkeypatch):
    monkeypatch.delenv("OPENCUT_IMAGE_GEN", raising=False)
    agent = ImageMatchingAgent(None, None, None)
    state = _state_with([{"text": "a"}, {"text": "b"}], [{"file": "i1.jpg"}, {"file": "i2.jpg"}])

    async def mock_match(p, i, ai):
        return {"0": {"image": "i1.jpg", "score": 0.9}, "1": {"image": "i2.jpg", "score": 0.8}}

    with patch("src.agents.image_matching_agent.match_images", new=mock_match):
        result = await agent.execute(state, state.get_stage("image_matching"))
    assert result["data"]["text_cards"] == []
    assert result["data"]["matches"]["0"] == "i1.jpg"
    assert result["data"]["matches"]["1"] == "i2.jpg"


@pytest.mark.asyncio
async def test_weak_match_layer1_reuse(monkeypatch):
    """0.4 ≤ s < 0.7 -> 第1层弱匹配复用（用匹配的图，不进文字卡）"""
    monkeypatch.delenv("OPENCUT_IMAGE_GEN", raising=False)
    agent = ImageMatchingAgent(None, None, None)
    state = _state_with([{"text": "a"}], [{"file": "i1.jpg"}])

    async def mock_match(p, i, ai):
        return {"0": {"image": "i1.jpg", "score": 0.5}}

    with patch("src.agents.image_matching_agent.match_images", new=mock_match):
        result = await agent.execute(state, state.get_stage("image_matching"))
    assert result["data"]["text_cards"] == []
    assert result["data"]["matches"]["0"] == "i1.jpg"


@pytest.mark.asyncio
async def test_gap_text_card_when_gen_disabled(monkeypatch):
    monkeypatch.delenv("OPENCUT_IMAGE_GEN", raising=False)
    agent = ImageMatchingAgent(None, None, None)
    state = _state_with([{"text": "a"}, {"text": "b"}], [{"file": "i1.jpg"}])

    async def mock_match(p, i, ai):
        return {"0": {"image": "i1.jpg", "score": 0.9}, "1": {"image": "", "score": 0.1}}

    with patch("src.agents.image_matching_agent.match_images", new=mock_match):
        result = await agent.execute(state, state.get_stage("image_matching"))
    assert 1 in result["data"]["text_cards"]  # 缺口 -> 文字卡
    assert result["data"]["matches"]["1"] == ""


@pytest.mark.asyncio
async def test_gap_gen_when_enabled_and_many(monkeypatch):
    """gen 开 + 缺口≥阈值 -> 第3层生图（mock generate_image）"""
    monkeypatch.setenv("OPENCUT_IMAGE_GEN", "1")
    monkeypatch.setattr("src.agents.image_matching_agent.GEN_TRIGGER_COUNT", 2)
    agent = ImageMatchingAgent(None, None, None)
    state = _state_with([{"text": "a"}, {"text": "b"}, {"text": "c"}], [{"file": "i1.jpg"}])

    async def mock_match(p, i, ai):
        return {"0": {"image": "i1.jpg", "score": 0.9},
                "1": {"image": "", "score": 0.1}, "2": {"image": "", "score": 0.1}}

    gen_called = []

    async def mock_gen(paragraph_text, ma_output, project_id, index):
        gen_called.append(index)
        return f"gen_{index}.jpg"

    with patch("src.agents.image_matching_agent.match_images", new=mock_match), \
         patch("src.tools.image_generator.generate_image", new=mock_gen):
        result = await agent.execute(state, state.get_stage("image_matching"))
    assert 1 not in result["data"]["text_cards"]
    assert 2 not in result["data"]["text_cards"]
    assert result["data"]["matches"]["1"] == "gen_1.jpg"
    assert sorted(gen_called) == [1, 2]


@pytest.mark.asyncio
async def test_gen_failure_falls_back_to_text_card(monkeypatch):
    monkeypatch.setenv("OPENCUT_IMAGE_GEN", "1")
    monkeypatch.setattr("src.agents.image_matching_agent.GEN_TRIGGER_COUNT", 1)
    agent = ImageMatchingAgent(None, None, None)
    state = _state_with([{"text": "a"}], [{"file": "i1.jpg"}])

    async def mock_match(p, i, ai):
        return {"0": {"image": "", "score": 0.1}}

    async def mock_gen(**kwargs):
        raise RuntimeError("gen fail")

    with patch("src.agents.image_matching_agent.match_images", new=mock_match), \
         patch("src.tools.image_generator.generate_image", new=mock_gen):
        result = await agent.execute(state, state.get_stage("image_matching"))
    assert 0 in result["data"]["text_cards"]  # gen 失败 -> 文字卡


@pytest.mark.asyncio
async def test_layer_log_recorded(monkeypatch):
    """每段决策写 layer_log，便于观测调参"""
    monkeypatch.delenv("OPENCUT_IMAGE_GEN", raising=False)
    agent = ImageMatchingAgent(None, None, None)
    state = _state_with([{"text": "a"}, {"text": "b"}], [{"file": "i1.jpg"}])

    async def mock_match(p, i, ai):
        return {"0": {"image": "i1.jpg", "score": 0.9}, "1": {"image": "", "score": 0.1}}

    with patch("src.agents.image_matching_agent.match_images", new=mock_match):
        result = await agent.execute(state, state.get_stage("image_matching"))
    log = result["data"]["layer_log"]
    assert len(log) == 2
    assert any("直接匹配" in l for l in log)
    assert any("文字卡" in l for l in log)
