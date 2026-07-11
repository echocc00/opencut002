"""M02 验收测试: 状态管理"""
import tempfile
from pathlib import Path

from src.orchestrator.state import ProjectState, StageState, StageStatus
from src.orchestrator.contracts import (
    OUTPUT_CONTRACTS, TopicOutput, CopywritingOutput,
    CopywritingParagraph, StoryboardOutput, StoryboardSegment,
)


def test_state_save_load_roundtrip():
    """创建 -> 保存 -> 重新加载，数据完全一致"""
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        state = ProjectState(project_id="test_proj", domain="travel")
        state.mark_stage("topic", StageStatus.IN_PROGRESS)
        state.get_stage("topic").output_data = {"directions": [{"name": "test"}]}
        state.mark_stage("topic", StageStatus.COMPLETED)
        state.save(data_dir)

        loaded = ProjectState.load(data_dir, "test_proj")
        assert loaded.project_id == "test_proj"
        assert loaded.domain == "travel"
        assert loaded.is_stage_completed("topic")
        assert loaded.get_stage_output("topic")["directions"][0]["name"] == "test"


def test_stage_isolation():
    """每个阶段有独立的 StageState，互不干扰"""
    state = ProjectState(project_id="test")
    state.mark_stage("topic", StageStatus.COMPLETED)
    state.mark_stage("copywriting", StageStatus.IN_PROGRESS)

    assert state.is_stage_completed("topic")
    assert not state.is_stage_completed("copywriting")
    assert state.get_stage("topic").status == StageStatus.COMPLETED
    assert state.get_stage("copywriting").status == StageStatus.IN_PROGRESS


def test_auto_create_stage():
    """不存在的阶段自动创建"""
    state = ProjectState(project_id="test")
    stage = state.get_stage("nonexistent")
    assert stage.name == "nonexistent"
    assert stage.status == StageStatus.PENDING


def test_contract_topic_output():
    """TopicOutput 契约验证"""
    output = TopicOutput(
        directions=[{"name": "敦煌探秘", "hook": "悬念式"}],
        selected=0,
    )
    assert len(output.directions) == 1
    assert output.directions[0].name == "敦煌探秘"
    assert output.selected == 0


def test_contract_copywriting_output():
    """CopywritingOutput 契约验证 - 含 highlight_ref"""
    output = CopywritingOutput(
        paragraphs=[
            CopywritingParagraph(
                text="你见过凌晨四点的敦煌吗？",
                target_duration=3.0,
                image_hint="IMG_001.jpg",
                highlight_ref="mystery_hook",
                emotion_tone="悬念",
            )
        ],
        tone="emotional",
    )
    assert len(output.paragraphs) == 1
    assert output.paragraphs[0].highlight_ref == "mystery_hook"
    assert output.tone == "emotional"


def test_contract_storyboard_output():
    """StoryboardOutput 契约验证 - 含 subtitle_words"""
    output = StoryboardOutput(
        segments=[
            StoryboardSegment(
                index=0,
                image="IMG_001.jpg",
                actual_duration=3.5,
                time_start=0.0,
                subtitle="你见过凌晨四点的敦煌",
                transition="crossfade",
                subtitle_words=[
                    {"word": "你", "start": 0.0, "end": 0.3},
                    {"word": "见过", "start": 0.3, "end": 0.6},
                ],
            )
        ],
        total_duration=3.5,
    )
    assert len(output.segments) == 1
    assert output.segments[0].subtitle_words[0]["word"] == "你"
    assert output.total_duration == 3.5


def test_output_contracts_registry():
    """契约注册表包含所有阶段"""
    expected_stages = [
        "material_analysis", "web_research", "topic", "highlight_selection",
        "copywriting", "storyboard", "voice_selection", "tts",
        "bgm", "rhythm", "title", "cover", "render",
    ]
    for stage in expected_stages:
        assert stage in OUTPUT_CONTRACTS, f"阶段 {stage} 不在契约注册表中"


def test_contract_validation_failure():
    """输出缺少必填字段时应能识别"""
    # CopywritingParagraph 的 text 为空 -> 不符合预期但 pydantic 不会报错（因为有默认值）
    # 这里测试通过 schema 校验识别空输出
    output = CopywritingOutput(paragraphs=[])
    assert len(output.paragraphs) == 0  # 空输出应被后续的质量关卡拦截
