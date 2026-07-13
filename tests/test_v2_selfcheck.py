"""第三轮自查：数据流完整性 + 集成问题验证"""
import tempfile
from pathlib import Path

import pytest
from src.orchestrator.state import ProjectState, StageStatus


class TestDataChainCopywriting:
    """copywriting 阶段注入 confirmed_highlights"""

    @pytest.mark.asyncio
    async def test_copywriting_gets_confirmed_highlights(self):
        from src.orchestrator.engine import PipelineEngine
        from src.agents.skill_loader import SkillLoader
        from src.agents.decision_logger import DecisionLogger
        from src.providers.selector import ProviderSelector
        from src.providers.provider_registry import register_provider, Provider, clear_registry
        from src.config import DomainConfig

        clear_registry()
        async def mock_complete(prompt: str, **kw) -> str:
            # 注意：paragraphs 必须先于 directions 判断——copywriting 的 upstream_context
            # 含 topic 的 directions 输出，会误匹配。R04 后 postflight 阻断空 paragraphs。
            if '"paragraphs"' in prompt:
                return '{"paragraphs": [{"text": "test", "target_duration": 3.0, "image_hint": "img.jpg", "highlight_ref": "mystery_hook", "emotion_tone": "悬念"}], "tone": "emotional"}'
            if '"directions"' in prompt:
                return '{"directions": [{"name":"test","hook":"suspense","psychology":"x","ref_type":"x","why_work":"x"}], "selected": 0}'
            if '"highlight_ids"' in prompt:
                return '{"options": [{"highlight_ids": ["mystery_hook"], "highlight_names": ["悬念"], "selection_reason": "x", "presentation_style": "悬念式", "expected_effect": "x"}], "selected": 0}'
            return '{}'
        for n in ["deepseek", "doubao", "qwen"]:
            register_provider(n, Provider(n, mock_complete))

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            eng = PipelineEngine(data_dir=data_dir)
            config = DomainConfig(Path("domains/travel"))
            eng.auto_register_handlers(
                SkillLoader(config), ProviderSelector(), DecisionLogger(data_dir, "test")
            )
            state = ProjectState(project_id="test", domain="travel", approval_mode="full_auto")
            # 模拟前置阶段完成
            state.mark_stage("material_analysis", StageStatus.COMPLETED)
            state.get_stage("material_analysis").output_data = {"images": [{"file": "img.jpg"}], "destination": "敦煌"}
            state.mark_stage("web_research", StageStatus.COMPLETED)
            state.get_stage("web_research").output_data = {"hot_topics": ["test"]}
            state.mark_stage("topic", StageStatus.COMPLETED)
            state.get_stage("topic").output_data = {"directions": [{"name": "test", "hook": "suspense"}], "selected": 0}
            state.mark_stage("highlight_selection", StageStatus.COMPLETED)
            state.get_stage("highlight_selection").output_data = {
                "options": [{"highlight_ids": ["mystery_hook"], "highlight_names": ["悬念"], "presentation_style": "悬念式", "expected_effect": "x"}],
                "selected": 0
            }

            await eng.run(state)

            cw_stage = state.get_stage("copywriting")
            assert cw_stage.status == StageStatus.COMPLETED
            # confirmed_highlights 应该被注入
            assert "confirmed_highlights" in cw_stage.input_data
            assert cw_stage.input_data["confirmed_highlights"]["highlight_names"] == ["悬念"]


class TestDataChainVoiceSelection:
    """voice_selection 阶段注入 available_voices"""

    @pytest.mark.asyncio
    async def test_voice_gets_available_voices(self):
        from src.orchestrator.engine import PipelineEngine
        from src.agents.skill_loader import SkillLoader
        from src.agents.decision_logger import DecisionLogger
        from src.providers.selector import ProviderSelector
        from src.providers.provider_registry import register_provider, Provider, clear_registry
        from src.config import DomainConfig

        clear_registry()
        async def mock_complete(prompt: str, **kw) -> str:
            if '"voice_key"' in prompt:
                return '{"candidates": [{"voice_key": "magnetic_male", "reason": "test"}], "selected": "magnetic_male"}'
            return '{}'
        for n in ["deepseek", "doubao", "qwen"]:
            register_provider(n, Provider(n, mock_complete))

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            eng = PipelineEngine(data_dir=data_dir)
            config = DomainConfig(Path("domains/travel"))
            eng.auto_register_handlers(
                SkillLoader(config), ProviderSelector(), DecisionLogger(data_dir, "test")
            )
            state = ProjectState(project_id="test", domain="travel", approval_mode="full_auto")
            state.mark_stage("copywriting", StageStatus.COMPLETED)
            state.get_stage("copywriting").output_data = {"paragraphs": [{"text": "test"}], "tone": "emotional"}

            await eng.run(state)

            vs_stage = state.get_stage("voice_selection")
            assert vs_stage.status == StageStatus.COMPLETED
            assert "available_voices" in vs_stage.input_data
            assert "magnetic_male" in vs_stage.input_data["available_voices"]


class TestDataChainBGM:
    """bgm 阶段注入 available_bgm"""

    @pytest.mark.asyncio
    async def test_bgm_gets_available_bgm_list(self):
        from src.orchestrator.engine import PipelineEngine
        from src.agents.skill_loader import SkillLoader
        from src.agents.decision_logger import DecisionLogger
        from src.providers.selector import ProviderSelector
        from src.providers.provider_registry import register_provider, Provider, clear_registry
        from src.config import DomainConfig

        clear_registry()
        async def mock_complete(prompt: str, **kw) -> str:
            if '"selected_path"' in prompt:
                return '{"candidates": [{"path": "test.mp3", "category": "cinematic", "reason": "x"}], "selected_path": "test.mp3", "volume": 0.25}'
            return '{}'
        for n in ["deepseek", "doubao", "qwen"]:
            register_provider(n, Provider(n, mock_complete))

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            eng = PipelineEngine(data_dir=data_dir)
            config = DomainConfig(Path("domains/travel"))
            eng.auto_register_handlers(
                SkillLoader(config), ProviderSelector(), DecisionLogger(data_dir, "test")
            )
            state = ProjectState(project_id="test", domain="travel", approval_mode="full_auto")
            state.mark_stage("storyboard", StageStatus.COMPLETED)
            state.get_stage("storyboard").output_data = {"segments": [{"image": "img.jpg", "actual_duration": 3.0}]}

            await eng.run(state)

            bgm_stage = state.get_stage("bgm")
            # bgm 可能完成也可能因为没有BGM文件而跳过
            assert "available_bgm" in bgm_stage.input_data


class TestPostflightIntegration:
    """postflight validate_output 被引擎调用"""

    def test_engine_calls_validate_output(self):
        from src.orchestrator.engine import PipelineEngine
        import inspect
        src = inspect.getsource(PipelineEngine.run)
        assert "validate_output" in src
        assert "postflight" in src


class TestE2EImportPath:
    """E2E测试使用新的import路径"""

    def test_e2e_uses_new_paths(self):
        content = open("tests/test_m23_e2e.py", encoding="utf-8").read()
        assert "highlight_selection_agent" in content
        assert "highlight_agent" not in content.replace("highlight_selection_agent", "")


class TestConcurrencyControl:
    """并发控制（v0.4.0 改为 Job 模型 + 线程池，不再用进程内 set）"""

    def test_run_delegates_to_job_runner(self):
        content = open("src/api/project_routes.py", encoding="utf-8").read()
        assert "start_job_for_project" in content  # /run 委派给 job runner
        assert "404" in content  # ownership 校验返回 404
