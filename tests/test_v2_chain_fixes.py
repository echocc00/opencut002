"""第二轮断链修复验证"""
import tempfile
from pathlib import Path

import pytest
from src.orchestrator.state import ProjectState, StageStatus


class TestChain2_StateLoadNone:
    """断链2: ProjectState.load 返回 None"""

    def test_load_nonexistent_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ProjectState.load(Path(tmp), "nonexistent")
            assert result is None

    def test_load_existing_returns_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = ProjectState(project_id="test", domain="travel")
            state.save(Path(tmp))
            loaded = ProjectState.load(Path(tmp), "test")
            assert loaded is not None
            assert loaded.project_id == "test"


class TestChain3_HighlightInjection:
    """断链3: highlight_selection 注入 highlights"""

    def test_engine_injects_highlights(self):
        """引擎在 highlight_selection 阶段前注入 highlights"""
        import asyncio
        from src.orchestrator.engine import PipelineEngine
        from src.agents.skill_loader import SkillLoader
        from src.agents.decision_logger import DecisionLogger
        from src.providers.selector import ProviderSelector
        from src.providers.provider_registry import register_provider, Provider, clear_registry
        from src.config import DomainConfig

        clear_registry()
        async def mock_complete(prompt: str, **kw) -> str:
            if '"directions"' in prompt:
                return '{"directions": [{"name":"test","hook":"suspense","psychology":"x","ref_type":"x","why_work":"x"}], "selected": 0}'
            if '"highlight_ids"' in prompt:
                return '{"options": [{"highlight_ids": ["mystery_hook"], "highlight_names": ["test"], "selection_reason": "x", "presentation_style": "x", "expected_effect": "x"}], "selected": 0}'
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
            # 模拟 material_analysis 和 topic 已完成
            state.mark_stage("material_analysis", StageStatus.COMPLETED)
            state.get_stage("material_analysis").output_data = {"images": [{"file": "img.jpg"}], "destination": "敦煌"}
            state.mark_stage("web_research", StageStatus.COMPLETED)
            state.get_stage("web_research").output_data = {"hot_topics": ["test"]}
            state.mark_stage("topic", StageStatus.COMPLETED)
            state.get_stage("topic").output_data = {"directions": [{"name": "test"}], "selected": 0}

            asyncio.run(eng.run(state))

            # highlight_selection 应该完成
            hl_stage = state.get_stage("highlight_selection")
            assert hl_stage.status == StageStatus.COMPLETED
            # input_data 应该有 highlights
            assert len(hl_stage.input_data.get("highlights", [])) > 0


class TestChain1_WordTimestamps:
    """断链1: word_timestamps 合并到 segments"""

    def test_merge_word_timestamps(self):
        from src.agents.render_agent import RenderAgent
        from src.agents.skill_loader import SkillLoader
        from src.agents.decision_logger import DecisionLogger
        from src.providers.selector import ProviderSelector
        from src.config import DomainConfig

        with tempfile.TemporaryDirectory() as tmp:
            config = DomainConfig(Path("domains/travel"))
            agent = RenderAgent(
                SkillLoader(config), ProviderSelector(), DecisionLogger(Path(tmp), "test")
            )
            segments = [
                {"index": 0, "image": "img1.jpg", "actual_duration": 3.0, "time_start": 0.0, "subtitle": "你好世界"},
                {"index": 1, "image": "img2.jpg", "actual_duration": 3.0, "time_start": 3.0, "subtitle": "测试文本"},
            ]
            word_timestamps = [
                {"word": "你", "start": 0.0, "end": 0.3},
                {"word": "好", "start": 0.3, "end": 0.6},
                {"word": "世", "start": 0.6, "end": 0.9},
                {"word": "界", "start": 0.9, "end": 1.2},
                {"word": "测", "start": 3.0, "end": 3.3},
                {"word": "试", "start": 3.3, "end": 3.6},
                {"word": "文", "start": 3.6, "end": 3.9},
                {"word": "本", "start": 3.9, "end": 4.2},
            ]
            merged = agent._merge_word_timestamps(segments, word_timestamps)
            assert len(merged[0]["subtitle_words"]) == 4
            assert merged[0]["subtitle_words"][0]["word"] == "你"
            assert merged[0]["subtitle_words"][0]["start"] == 0.0  # 相对于段开始
            assert len(merged[1]["subtitle_words"]) == 4
            assert merged[1]["subtitle_words"][0]["word"] == "测"
            assert merged[1]["subtitle_words"][0]["start"] == 0.0  # 相对于段开始(3.0-3.0=0.0)


class TestApproveRecordsDecision:
    """approve_stage 调用 record_decision"""

    def test_engine_holds_preference_profile(self):
        from src.orchestrator.engine import PipelineEngine
        from src.orchestrator.preference_profile import PreferenceProfile
        from src.agents.skill_loader import SkillLoader
        from src.agents.decision_logger import DecisionLogger
        from src.providers.selector import ProviderSelector
        from src.config import DomainConfig

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            eng = PipelineEngine(data_dir=data_dir)
            config = DomainConfig(Path("domains/travel"))
            profile = PreferenceProfile(data_dir, "default")
            eng.auto_register_handlers(
                SkillLoader(config), ProviderSelector(), DecisionLogger(data_dir, "test"),
                preference_profile=profile,
            )
            assert eng.preference_profile is profile

    @pytest.mark.asyncio
    async def test_approve_calls_record_decision(self):
        from src.orchestrator.engine import PipelineEngine
        from src.orchestrator.preference_profile import PreferenceProfile
        from src.agents.skill_loader import SkillLoader
        from src.agents.decision_logger import DecisionLogger
        from src.providers.selector import ProviderSelector
        from src.providers.provider_registry import clear_registry, register_provider, Provider
        from src.config import DomainConfig

        clear_registry()
        async def mock(p, **k): return '{}'
        for n in ["deepseek", "doubao", "qwen"]:
            register_provider(n, Provider(n, mock))

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            eng = PipelineEngine(data_dir=data_dir)
            config = DomainConfig(Path("domains/travel"))
            profile = PreferenceProfile(data_dir, "default")
            eng.auto_register_handlers(
                SkillLoader(config), ProviderSelector(), DecisionLogger(data_dir, "test"),
                preference_profile=profile,
            )
            state = ProjectState(project_id="test", domain="travel", approval_mode="manual")
            stage = state.get_stage("topic")
            stage.status = StageStatus.REVIEW
            stage.output_data = {"directions": [{"hook": "suspense"}]}
            state.save(data_dir)

            await eng.approve_stage(state, "topic", approved=True)

            assert profile.data["total_videos_produced"] == 1
            assert profile.data["preferred_hook_style"] == "suspense"


class TestPanelRoutesPaths:
    """panel_routes 不硬编码路径"""

    def test_uses_get_settings(self):
        content = open("src/api/panel_routes.py", encoding="utf-8").read()
        assert "get_settings" in content
        assert 'Path("data/projects' not in content
        assert 'Path(f"data/projects' not in content
