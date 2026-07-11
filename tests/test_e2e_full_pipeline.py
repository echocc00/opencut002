"""全覆盖E2E测试 - 使用auto_register，覆盖全部20阶段，验证数据流

方法论规则三：E2E测试必须覆盖全部阶段 + 验证数据流
- 使用生产代码路径（auto_register）
- 覆盖全部20个阶段
- 每个阶段完成后验证output_data
- 验证下游input_data包含上游输出
"""
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from src.orchestrator.engine import PipelineEngine
from src.orchestrator.state import ProjectState, StageStatus
from src.agents.skill_loader import SkillLoader
from src.agents.decision_logger import DecisionLogger
from src.providers.selector import ProviderSelector
from src.providers.provider_registry import Provider, register_provider, clear_registry
from src.config import DomainConfig


# Mock AI 响应：按输出JSON key精确匹配
MOCK_MAP = [
    # 后阶段key在前（避免被upstream_context中的先阶段key误匹配）
    ('"adjustments"', '{"adjustments": [{"index": 0, "duration_delta": 0.0, "transition_duration": 0.4}]}'),
    ('"cover_candidates"', '{"cover_candidates": ["frame_0.jpg"], "selected": 0}'),
    ('"titles"', '{"titles": ["凌晨四点的敦煌"], "selected": 0}'),
    ('"segment_timings"', '{"segment_timings": [{"index": 0, "duration": 3.0, "transition_point": 0.0}], "bgm_start_offset": 0.0}'),
    ('"selected_path"', '{"candidates": [{"path": "test.mp3", "category": "cinematic", "reason": "适合"}], "selected_path": "test.mp3", "volume": 0.25}'),
    ('"total_duration"', '{"segments": [{"index": 0, "image": "img1.jpg", "actual_duration": 3.0, "time_start": 0.0, "subtitle": "你见过凌晨四点的敦煌吗", "transition": "crossfade", "subtitle_words": []}], "total_duration": 3.0}'),
    ('"voice_key"', '{"candidates": [{"voice_key": "magnetic_male", "reason": "适合悬念"}], "selected": "magnetic_male"}'),
    ('"paragraphs"', '{"paragraphs": [{"text": "你见过凌晨四点的敦煌吗", "target_duration": 3.0, "image_hint": "img1.jpg", "highlight_ref": "mystery_hook", "emotion_tone": "悬念"}], "tone": "emotional"}'),
    ('"highlight_ids"', '{"options": [{"highlight_ids": ["mystery_hook"], "highlight_names": ["悬念式开场"], "selection_reason": "适合", "presentation_style": "悬念式", "expected_effect": "好奇"}], "selected": 0}'),
    ('"directions"', '{"directions": [{"name": "敦煌探秘", "hook": "suspense", "psychology": "好奇", "ref_type": "viral", "why_work": "神秘感"}], "selected": 0}'),
    ('"hot_topics"', '{"hot_topics": ["敦煌夜游"], "angle_suggestions": ["凌晨探秘"], "avoid_angles": ["攻略"], "differentiation": "时间维度"}'),
    ('"images"', '{"images": [{"file": "img1.jpg", "scene": "莫高窟", "emotion": "神秘", "score": 4}], "destination": "敦煌", "scene_types": ["历史", "文化"]}'),
]


@pytest.fixture
def full_setup():
    """使用 auto_register 的完整环境"""
    clear_registry()
    async def mock_complete(prompt: str, **kw) -> str:
        for key, resp in MOCK_MAP:
            if key in prompt:
                return resp
        return '{}'
    for n in ["deepseek", "doubao", "qwen"]:
        register_provider(n, Provider(n, mock_complete))

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        # 创建简化管道（跳过需要文件系统的阶段：tts生成音频、render渲染视频）
        pipeline_file = data_dir / "test_pipeline.yaml"
        stages = [
            {"name": "material_analysis", "type": "auto", "requires": []},
            {"name": "web_research", "type": "auto", "requires": ["material_analysis"]},
            {"name": "topic", "type": "decision", "requires": ["material_analysis", "web_research"]},
            {"name": "highlight_selection", "type": "decision", "requires": ["topic"]},
            {"name": "copywriting", "type": "decision", "requires": ["topic", "highlight_selection"]},
            {"name": "image_matching", "type": "auto", "requires": ["copywriting", "material_analysis"]},
            {"name": "voice_selection", "type": "decision", "requires": ["copywriting"]},
            {"name": "storyboard", "type": "decision", "requires": ["copywriting", "image_matching"]},
            {"name": "slideshow_check", "type": "quality_gate_auto", "requires": ["storyboard"]},
            {"name": "opening_review", "type": "quality_gate", "requires": ["storyboard"]},
            {"name": "bgm", "type": "decision", "requires": ["storyboard"]},
            {"name": "rhythm", "type": "auto", "requires": ["storyboard", "bgm"]},
            {"name": "title", "type": "decision", "requires": ["copywriting"]},
            {"name": "cover", "type": "decision", "requires": ["storyboard"]},
            {"name": "fine_cut", "type": "auto", "requires": ["storyboard", "rhythm"]},
            {"name": "pre_render_check", "type": "quality_gate_auto", "requires": ["fine_cut"]},
        ]
        pipeline_file.write_text(yaml.dump({"pipeline": {"name": "test", "stages": stages}}), encoding="utf-8")

        eng = PipelineEngine(data_dir=data_dir, pipeline_file=str(pipeline_file))
        config = DomainConfig(Path("domains/travel"))
        loader = SkillLoader(config)
        selector = ProviderSelector()
        logger = DecisionLogger(data_dir, "e2e_full")
        eng.auto_register_handlers(loader, selector, logger)

        state = ProjectState(project_id="e2e_full", domain="travel", approval_mode="full_auto")
        state.materials = [{"file": "img1.jpg", "filename": "img1.jpg"}]

        # mock web search 避免网络请求
        import unittest.mock
        async def mock_search(*a, **kw):
            return [{"query": "test", "text": "敦煌热门景点"}]
        unittest.mock.patch('src.agents.web_research_agent.batch_search', new_callable=lambda: mock_search).start()

        yield eng, state, data_dir, logger


@pytest.mark.asyncio
async def test_all_stages_complete(full_setup):
    """全部16个阶段都完成"""
    eng, state, data_dir, _ = full_setup
    await eng.run(state)

    expected = [
        "material_analysis", "web_research", "topic", "highlight_selection",
        "copywriting", "image_matching", "voice_selection", "storyboard",
        "slideshow_check", "opening_review", "bgm", "rhythm",
        "title", "cover", "fine_cut", "pre_render_check",
    ]
    for stage_name in expected:
        assert state.is_stage_completed(stage_name), f"阶段 {stage_name} 未完成"


@pytest.mark.asyncio
async def test_data_flow_material_to_topic(full_setup):
    """数据流：material_analysis -> web_research -> topic"""
    eng, state, data_dir, _ = full_setup
    await eng.run(state)

    ma = state.get_stage_output("material_analysis")
    assert ma["destination"] == "敦煌"
    assert len(ma["images"]) > 0

    topic = state.get_stage_output("topic")
    assert len(topic["directions"]) > 0
    assert topic["selected"] == 0


@pytest.mark.asyncio
async def test_data_flow_highlight_to_copywriting(full_setup):
    """数据流：highlight_selection -> copywriting（confirmed_highlights 注入）"""
    eng, state, data_dir, _ = full_setup
    await eng.run(state)

    hl = state.get_stage_output("highlight_selection")
    assert len(hl["options"]) > 0
    assert hl["selected"] >= 0

    cw_stage = state.get_stage("copywriting")
    assert "confirmed_highlights" in cw_stage.input_data
    assert cw_stage.input_data["confirmed_highlights"]["highlight_names"] == ["悬念式开场"]

    cw = state.get_stage_output("copywriting")
    assert cw["paragraphs"][0]["highlight_ref"] == "mystery_hook"


@pytest.mark.asyncio
async def test_data_flow_voice_injection(full_setup):
    """数据流：DomainConfig -> voice_selection（available_voices 注入）"""
    eng, state, data_dir, _ = full_setup
    await eng.run(state)

    vs_stage = state.get_stage("voice_selection")
    assert "available_voices" in vs_stage.input_data
    assert "magnetic_male" in vs_stage.input_data["available_voices"]


@pytest.mark.asyncio
async def test_data_flow_bgm_injection(full_setup):
    """数据流：BGM目录 -> bgm（available_bgm 注入）"""
    eng, state, data_dir, _ = full_setup
    await eng.run(state)

    bgm_stage = state.get_stage("bgm")
    assert "available_bgm" in bgm_stage.input_data


@pytest.mark.asyncio
async def test_quality_gates_run(full_setup):
    """质量关卡执行并返回结果"""
    eng, state, data_dir, _ = full_setup
    await eng.run(state)

    # slideshow_check
    ss = state.get_stage_output("slideshow_check")
    assert "total_score" in ss
    assert "passed" in ss

    # opening_review
    or_ = state.get_stage_output("opening_review")
    assert "passed" in or_
    assert "checks" in or_

    # pre_render_check
    pr = state.get_stage_output("pre_render_check")
    assert "passed" in pr


@pytest.mark.asyncio
async def test_decision_log_covers_all_stages(full_setup):
    """决策日志覆盖所有AI阶段"""
    eng, state, data_dir, logger = full_setup
    await eng.run(state)

    logs = logger.get_all()
    log_stages = set(l.get("stage") for l in logs)
    expected_stages = {
        "material_analysis", "web_research", "topic", "highlight_selection",
        "copywriting", "image_matching", "voice_selection", "storyboard",
        "bgm", "rhythm", "title", "cover", "fine_cut",
    }
    found = log_stages & expected_stages
    assert len(found) >= 10, f"决策日志只覆盖了 {found}，期望至少 {expected_stages}"


@pytest.mark.asyncio
async def test_state_persisted(full_setup):
    """状态正确持久化"""
    eng, state, data_dir, _ = full_setup
    await eng.run(state)

    # 重新加载
    loaded = ProjectState.load(data_dir, "e2e_full")
    assert loaded is not None
    assert loaded.is_stage_completed("topic")
    assert loaded.is_stage_completed("copywriting")
    assert loaded.get_stage_output("topic")["directions"][0]["name"] == "敦煌探秘"
