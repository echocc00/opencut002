"""M03 验收测试: 管道引擎"""
import tempfile
from pathlib import Path

import pytest
import yaml

from src.orchestrator.engine import PipelineEngine
from src.orchestrator.approval_controller import should_pause_for_review
from src.orchestrator.state import ProjectState, StageStatus


@pytest.fixture
def engine():
    with tempfile.TemporaryDirectory() as tmp:
        eng = PipelineEngine(data_dir=Path(tmp))
        yield eng


def test_pipeline_yaml_loads(engine):
    """YAML 管道清单能正确加载，包含全部 20 个阶段"""
    stages = engine.get_stages()
    assert len(stages) == 20
    names = [s["name"] for s in stages]
    assert "material_analysis" in names
    assert "topic" in names
    assert "render" in names
    assert "deliver" in names


def test_stage_order(engine):
    """阶段顺序正确"""
    stages = engine.get_stages()
    names = [s["name"] for s in stages]
    assert names.index("material_analysis") < names.index("topic")
    assert names.index("topic") < names.index("copywriting")
    assert names.index("storyboard") < names.index("bgm")
    assert names.index("render") < names.index("deliver")


def test_prerequisites_check(engine):
    """前置条件不满足时跳过"""
    state = ProjectState(project_id="test")
    stage_def = {"name": "topic", "requires": ["material_analysis", "web_research"]}
    assert not engine._check_prerequisites(state, stage_def)

    state.mark_stage("material_analysis", StageStatus.COMPLETED)
    assert not engine._check_prerequisites(state, stage_def)

    state.mark_stage("web_research", StageStatus.COMPLETED)
    assert engine._check_prerequisites(state, stage_def)


def test_manual_mode_needs_review(engine):
    """手动模式下 decision 类型暂停在 REVIEW"""
    assert should_pause_for_review("decision", "manual", None) is True
    assert should_pause_for_review("quality_gate", "manual", None) is True
    assert should_pause_for_review("manual", "manual", None) is True
    assert should_pause_for_review("auto", "manual", None) is False
    assert should_pause_for_review("quality_gate_auto", "manual", None) is False


def test_full_auto_no_review(engine):
    """全自动模式下所有阶段不暂停"""
    assert should_pause_for_review("decision", "full_auto", None) is False
    assert should_pause_for_review("quality_gate", "full_auto", None) is False
    assert should_pause_for_review("manual", "full_auto", None) is False


def test_semi_auto_confidence_based(engine):
    """半自动模式：高置信度自动通过，低置信度需确认"""
    assert should_pause_for_review("decision", "semi_auto", 85) is False
    assert should_pause_for_review("decision", "semi_auto", 60) is True
    assert should_pause_for_review("decision", "semi_auto", None) is True
    # quality_gate 和 manual 始终需要确认
    assert should_pause_for_review("quality_gate", "semi_auto", 95) is True


@pytest.mark.asyncio
async def test_engine_runs_auto_stages(engine, tmp_path):
    """注册 mock handler -> 运行管道 -> auto 阶段执行"""
    async def mock_handler(state, stage):
        if stage.name == "material_analysis":
            return {"data": {"images": [{"file": "img.jpg"}], "destination": "test",
                             "result": f"output of {stage.name}"}, "confidence": 75.0}
        return {"data": {"hot_topics": ["test"], "result": f"output of {stage.name}"}, "confidence": 75.0}

    engine.data_dir = tmp_path
    # 只注册前 3 个阶段（全是 auto）
    for name in ["material_analysis", "web_research"]:
        engine.register_handler(name, mock_handler)

    state = ProjectState(project_id="test", approval_mode="full_auto")
    # 简化：只运行前 2 个阶段
    engine.pipeline["pipeline"]["stages"] = engine.get_stages()[:2]
    await engine.run(state)

    assert state.is_stage_completed("material_analysis")
    assert state.is_stage_completed("web_research")
    assert state.get_stage_output("material_analysis")["result"] == "output of material_analysis"


@pytest.mark.asyncio
async def test_engine_error_handling(engine, tmp_path):
    """阶段失败时状态标记为 ERROR"""
    async def failing_handler(state, stage):
        raise RuntimeError("intentional failure")

    engine.data_dir = tmp_path
    engine.register_handler("material_analysis", failing_handler)
    engine.pipeline["pipeline"]["stages"] = engine.get_stages()[:1]

    state = ProjectState(project_id="test", approval_mode="full_auto")
    with pytest.raises(RuntimeError):
        await engine.run(state)

    assert state.get_stage("material_analysis").status == StageStatus.ERROR
    assert "intentional failure" in state.get_stage("material_analysis").error
