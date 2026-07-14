"""C2 文案驱动模式测试：structure_script 切分 + ScriptInputAgent + script_first 管道"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.agents.script_input_agent import ScriptInputAgent, structure_script


# ========== structure_script ==========

def test_structure_script_packs_short_sentences():
    """短句贪心打包成一段（≤40 字）"""
    paras = structure_script("你好。世界。测试。")
    assert len(paras) == 1
    assert paras[0]["text"] == "你好。世界。测试。"


def test_structure_script_splits_long_text():
    """长文本切成多段，每段 ≤40 字"""
    text = "第一句比较长的内容大概有十几个字左右。第二句也比较长差不多同样长度。第三句还是这样的长度内容。"
    paras = structure_script(text)
    assert len(paras) >= 2
    for p in paras:
        assert len(p["text"]) <= 40


def test_structure_script_hard_splits_overlong_sentence():
    """超长单句硬切成 ≤40"""
    text = "a" * 50 + "。"
    paras = structure_script(text)
    assert len(paras) >= 2
    for p in paras:
        assert len(p["text"]) <= 40


def test_structure_script_assigns_defaults():
    paras = structure_script("测试文案。")
    assert len(paras) == 1
    p = paras[0]
    assert p["image_hint"] == ""
    assert p["highlight_ref"] == ""
    assert p["emotion_tone"] == "neutral"
    assert p["target_duration"] > 0


def test_structure_script_empty():
    assert structure_script("") == []
    assert structure_script("   ") == []


def test_structure_script_newline_breaks():
    """换行也作为断句点"""
    paras = structure_script("第一段内容\n第二段内容")
    assert len(paras) >= 1
    # 两个短段可能打包成一段，也可能分两段（取决于长度），都合法
    full = "".join(p["text"] for p in paras)
    assert "第一段" in full and "第二段" in full


# ========== ScriptInputAgent.execute ==========

@pytest.mark.asyncio
async def test_script_input_agent_execute_returns_paragraphs():
    agent = ScriptInputAgent(None, None, None)  # deps 未使用
    from src.orchestrator.state import ProjectState
    state = ProjectState(project_id="test", domain="education")
    stage = state.get_stage("copywriting")
    stage.input_data = {"user_script": "这是第一句文案。这是第二句文案内容。"}
    result = await agent.execute(state, stage)
    assert "paragraphs" in result["data"]
    assert len(result["data"]["paragraphs"]) >= 1
    assert result["data"]["tone"] == "neutral"
    assert result["confidence"] >= 80
    # 每段有 copywriting 契约字段
    for p in result["data"]["paragraphs"]:
        assert "text" in p and "target_duration" in p and "emotion_tone" in p


@pytest.mark.asyncio
async def test_script_input_agent_empty_script():
    agent = ScriptInputAgent(None, None, None)
    from src.orchestrator.state import ProjectState
    state = ProjectState(project_id="test", domain="education")
    stage = state.get_stage("copywriting")
    stage.input_data = {"user_script": ""}
    result = await agent.execute(state, stage)
    assert result["data"]["paragraphs"] == []
    assert result["confidence"] < 50


# ========== script_first 管道结构 ==========

def test_script_first_pipeline_skips_topic_highlight_webresearch():
    """script_first 管道跳过 web_research/topic/highlight，保留 copywriting/image_matching"""
    from src.orchestrator.engine import PipelineEngine
    eng = PipelineEngine(data_dir=Path("data"), pipeline_file="pipelines/script_first.yaml")
    stages = [s["name"] for s in eng.get_stages()]
    assert "web_research" not in stages
    assert "topic" not in stages
    assert "highlight_selection" not in stages
    assert "material_analysis" in stages
    assert "copywriting" in stages
    assert "image_matching" in stages
    assert "tts" in stages
    assert "render" in stages


def test_script_first_copywriting_requires_material_analysis_only():
    """copywriting 的 requires 只含 material_analysis（不依赖 topic/highlight）"""
    from src.orchestrator.engine import PipelineEngine
    eng = PipelineEngine(data_dir=Path("data"), pipeline_file="pipelines/script_first.yaml")
    cw = next(s for s in eng.get_stages() if s["name"] == "copywriting")
    assert cw.get("requires") == ["material_analysis"]
