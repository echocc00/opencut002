"""验证修复后的集成：自动注册+质量关卡+approve+FastAPI"""
import tempfile
from pathlib import Path

import pytest

from src.orchestrator.engine import PipelineEngine
from src.orchestrator.state import ProjectState, StageStatus
from src.agents.skill_loader import SkillLoader
from src.agents.decision_logger import DecisionLogger
from src.providers.selector import ProviderSelector
from src.providers.provider_registry import Provider, register_provider, clear_registry
from src.config import DomainConfig


@pytest.fixture
def engine_setup():
    clear_registry()
    async def mock_complete(prompt: str, **kw) -> str:
        if '"directions"' in prompt:
            return '{"directions": [{"name": "test", "hook": "suspense", "psychology": "x", "ref_type": "x", "why_work": "x"}], "selected": 0}'
        return '{}'
    for n in ["deepseek", "doubao", "qwen"]:
        register_provider(n, Provider(n, mock_complete))

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        eng = PipelineEngine(data_dir=data_dir)
        config = DomainConfig(Path("domains/travel"))
        loader = SkillLoader(config)
        selector = ProviderSelector()
        logger = DecisionLogger(data_dir, "test")
        eng.auto_register_handlers(loader, selector, logger)
        yield eng, data_dir, logger


class TestAutoRegistration:
    def test_all_20_stages_have_handlers(self, engine_setup):
        """所有20个阶段都注册了handler"""
        eng, _, _ = engine_setup
        pipeline_stages = [s["name"] for s in eng.get_stages()]
        for name in pipeline_stages:
            assert name in eng.stage_handlers, f"阶段 {name} 没有注册handler"

    def test_quality_gate_handlers_registered(self, engine_setup):
        """质量关卡handler已注册"""
        eng, _, _ = engine_setup
        assert "slideshow_check" in eng.stage_handlers
        assert "opening_review" in eng.stage_handlers
        assert "pre_render_check" in eng.stage_handlers
        assert "post_render_check" in eng.stage_handlers
        assert "deliver" in eng.stage_handlers

    def test_material_analysis_agent_registered(self, engine_setup):
        eng, _, _ = engine_setup
        assert "material_analysis" in eng.stage_handlers

    def test_image_matching_agent_registered(self, engine_setup):
        eng, _, _ = engine_setup
        assert "image_matching" in eng.stage_handlers

    def test_tts_agent_registered(self, engine_setup):
        eng, _, _ = engine_setup
        assert "tts" in eng.stage_handlers


class TestApproveResume:
    @pytest.mark.asyncio
    async def test_approve_stage(self, engine_setup):
        """approve_stage 能审批REVIEW状态阶段"""
        eng, data_dir, _ = engine_setup
        state = ProjectState(project_id="test", approval_mode="manual")
        stage = state.get_stage("topic")
        stage.status = StageStatus.REVIEW
        state.save(data_dir)

        await eng.approve_stage(state, "topic", approved=True)
        assert state.is_stage_completed("topic")

    @pytest.mark.asyncio
    async def test_reject_stage(self, engine_setup):
        """拒绝后阶段回到PENDING"""
        eng, data_dir, _ = engine_setup
        state = ProjectState(project_id="test2", approval_mode="manual")
        stage = state.get_stage("topic")
        stage.status = StageStatus.REVIEW
        state.save(data_dir)

        await eng.approve_stage(state, "topic", approved=False, feedback="不好")
        assert state.get_stage("topic").status == StageStatus.PENDING
        assert state.get_stage("topic").retry_count == 1
        assert state.user_notes.get("topic") == "不好"


class TestFastAPIApp:
    def test_app_importable(self):
        """FastAPI app可导入"""
        from src.api.app import app
        assert app.title == "OpenCut v3.0"

    def test_project_routes_exist(self):
        """项目操作API路由存在"""
        from src.api.project_routes import router
        paths = [r.path for r in router.routes]
        assert any("/create" in p for p in paths)
        assert any("/run" in p for p in paths)
        assert any("/approve" in p for p in paths)
        assert any("/state" in p for p in paths)

    def test_dockerfile_uses_app(self):
        """Dockerfile CMD指向app.py"""
        content = Path("Dockerfile").read_text(encoding="utf-8")
        assert "src.api.app:app" in content


class TestP0Fixes:
    def test_confidence_scorer_is_used(self):
        """base_agent 使用 confidence_scorer 而非自己的计算"""
        from src.agents.base_agent import BaseStageAgent
        # 确认 _calculate_confidence 不再存在于 BaseStageAgent
        assert not hasattr(BaseStageAgent, "_calculate_confidence")

    def test_engine_uses_approval_controller(self):
        """引擎使用 approval_controller 而非自己的 _needs_review"""
        from src.orchestrator.engine import PipelineEngine
        assert not hasattr(PipelineEngine, "_needs_review")

    def test_input_json_uses_uuid(self):
        """remotion_renderer 使用 uuid 文件名"""
        content = Path("src/tools/remotion_renderer.py").read_text(encoding="utf-8")
        assert "uuid" in content

    def test_base_agent_accepts_optional_deps(self):
        """base_agent 接受 preference_profile 和 annotation_store"""
        from src.agents.base_agent import BaseStageAgent
        import inspect
        sig = inspect.signature(BaseStageAgent.__init__)
        assert "preference_profile" in sig.parameters
        assert "annotation_store" in sig.parameters
