"""pipeline 变体测试（v0.6.2+）：minimal / draft / topic_first。

关键安全检查：每个 stage 的 requires 只引用管道内存在的阶段（无悬空依赖）。
topic_first 验证契约跳过（web_research 不在管道 -> topic 的 web_research 要求自动豁免）。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.orchestrator.engine import PipelineEngine


def _stages(name: str) -> list[dict]:
    eng = PipelineEngine(data_dir=Path("data"), pipeline_file=f"pipelines/{name}.yaml")
    return eng.get_stages()


def _stage_names(name: str) -> set[str]:
    return {s["name"] for s in _stages(name)}


def _assert_no_dangling_requires(name: str):
    """每个 stage 的 requires 必须都在管道内（防 topic_first 类的悬空依赖）。"""
    stages = _stages(name)
    names = {s["name"] for s in stages}
    for s in stages:
        for req in s.get("requires", []):
            assert req in names, f"[{name}] stage {s['name']} requires '{req}' 不在管道内"


class TestMinimal:
    def test_loads(self):
        assert _stages("minimal")[0]["name"] == "material_analysis"

    def test_skips_title_cover(self):
        names = _stage_names("minimal")
        assert "title" not in names
        assert "cover" not in names

    def test_keeps_core(self):
        names = _stage_names("minimal")
        for needed in ["copywriting", "tts", "render", "deliver", "post_render_check"]:
            assert needed in names, f"minimal 应保留 {needed}"

    def test_no_dangling_requires(self):
        _assert_no_dangling_requires("minimal")

    def test_deliver_last(self):
        assert _stages("minimal")[-1]["name"] == "deliver"


class TestDraft:
    def test_skips_quality_gates(self):
        names = _stage_names("draft")
        for gate in ["opening_review", "slideshow_check", "pre_render_check"]:
            assert gate not in names, f"draft 应跳过 {gate}"

    def test_keeps_post_render_check_for_deliver(self):
        """deliver 依赖 post_render_check，必须保留。"""
        names = _stage_names("draft")
        assert "post_render_check" in names
        assert "deliver" in names

    def test_keeps_content_stages(self):
        names = _stage_names("draft")
        for needed in ["web_research", "topic", "copywriting", "tts", "render"]:
            assert needed in names

    def test_no_dangling_requires(self):
        _assert_no_dangling_requires("draft")


class TestTopicFirst:
    def test_skips_web_research(self):
        names = _stage_names("topic_first")
        assert "web_research" not in names

    def test_topic_requires_only_material_analysis(self):
        """topic.requires 不再含 web_research（已跳过）。"""
        stages = _stages("topic_first")
        topic = next(s for s in stages if s["name"] == "topic")
        assert topic["requires"] == ["material_analysis"]

    def test_no_dangling_requires(self):
        _assert_no_dangling_requires("topic_first")

    def test_topic_contract_skips_web_research(self):
        """topic_first：web_research 不在管道 -> topic 的 web_research.hot_topics 契约要求自动豁免。"""
        from src.quality.preflight import check_stage_inputs
        from src.orchestrator.state import ProjectState

        state = ProjectState(project_id="t", domain="education")
        # material_analysis 有 images，无 web_research 输出
        state.stages["material_analysis"] = type(state.get_stage("material_analysis"))(name="material_analysis")
        state.stages["material_analysis"].output_data = {"images": [{"file": "x.jpg"}]}
        state.stages["material_analysis"].status = "completed"

        available = _stage_names("topic_first")  # 不含 web_research
        ok, issues = check_stage_inputs(state, "topic", available_stages=available)
        assert ok, f"topic 契约应通过（web_research 豁免），实际 issues: {issues}"

    def test_topic_contract_fails_without_material_images(self):
        """对照：material_analysis.images 缺失仍应报错（契约有效）。"""
        from src.quality.preflight import check_stage_inputs
        from src.orchestrator.state import ProjectState

        state = ProjectState(project_id="t", domain="education")
        state.stages["material_analysis"] = type(state.get_stage("material_analysis"))(name="material_analysis")
        state.stages["material_analysis"].output_data = {"images": []}  # 空
        state.stages["material_analysis"].status = "completed"

        available = _stage_names("topic_first")
        ok, issues = check_stage_inputs(state, "topic", available_stages=available)
        assert not ok  # material_analysis.images 空 -> 报错


class TestAllVariants:
    """所有变体（含已有 default/script_first）公共性质。"""

    @pytest.mark.parametrize("name", ["default", "script_first", "minimal", "draft", "topic_first"])
    def test_loads_and_has_deliver(self, name):
        stages = _stages(name)
        assert stages[-1]["name"] == "deliver"
        assert stages[0]["name"] == "material_analysis"

    @pytest.mark.parametrize("name", ["default", "script_first", "minimal", "draft", "topic_first"])
    def test_no_dangling_requires(self, name):
        _assert_no_dangling_requires(name)
