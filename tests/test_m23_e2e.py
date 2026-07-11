"""M23 端到端集成测试: 全流程mock验证"""
import tempfile
from pathlib import Path

import pytest
import yaml

from src.orchestrator.engine import PipelineEngine
from src.orchestrator.state import ProjectState
from src.providers.provider_registry import Provider, register_provider, clear_registry
from src.agents.topic_agent import TopicAgent
from src.agents.highlight_selection_agent import HighlightAgent
from src.agents.copywriting_agent import CopywritingAgent
from src.agents.storyboard_agent import StoryboardAgent
from src.agents.title_agent import TitleAgent
from src.agents.skill_loader import SkillLoader
from src.agents.decision_logger import DecisionLogger
from src.providers.selector import ProviderSelector
from src.config import DomainConfig


@pytest.fixture
def e2e_setup():
    clear_registry()

    async def mock_complete(prompt: str, **kw) -> str:
        # 输出特定key优先检查（directions可能出现在上游上下文中）
        checks = [
            ('"total_duration"', '{"segments": [{"index": 0, "image": "img1.jpg", "actual_duration": 3.0, "time_start": 0.0, "subtitle": "你见过凌晨四点的敦煌", "transition": "crossfade", "subtitle_words": [{"word": "你", "start": 0.0, "end": 0.3}]}], "total_duration": 3.0}'),
            ('"paragraphs"', '{"paragraphs": [{"text": "你见过凌晨四点的敦煌", "target_duration": 3.0, "image_hint": "img1.jpg", "highlight_ref": "mystery_hook", "emotion_tone": "悬念"}], "tone": "emotional"}'),
            ('"total_duration"', '{"segments": [{"index": 0, "image": "img1.jpg", "actual_duration": 3.0, "time_start": 0.0, "subtitle": "你见过凌晨四点的敦煌", "transition": "crossfade", "subtitle_words": [{"word": "你", "start": 0.0, "end": 0.3}]}], "total_duration": 3.0}'),
            ('"highlight_ids"', '{"options": [{"highlight_ids": ["mystery_hook"], "highlight_names": ["悬念式开场"], "selection_reason": "适合", "presentation_style": "悬念式", "expected_effect": "好奇"}], "selected": 0}'),
            ('"directions"', '{"directions": [{"name": "敦煌探秘", "hook": "suspense", "psychology": "好奇", "ref_type": "viral", "why_work": "神秘感"}], "selected": 0}'),
        ]
        for key, resp in checks:
            if key in prompt:
                return resp
        return '{}'

    for name in ["deepseek", "doubao", "qwen"]:
        register_provider(name, Provider(name, mock_complete))

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        pipeline_file = data_dir / "test_pipeline.yaml"
        pipeline_file.write_text(yaml.dump({"pipeline": {"name": "test", "stages": [
            {"name": "topic", "type": "decision", "skill": "topic", "requires": []},
            {"name": "highlight_selection", "type": "decision", "skill": "highlight", "requires": ["topic"]},
            {"name": "copywriting", "type": "decision", "skill": "copywriting", "requires": ["topic", "highlight_selection"]},
            {"name": "storyboard", "type": "decision", "skill": "storyboard", "requires": ["copywriting"]},
            {"name": "title", "type": "decision", "skill": "title", "requires": ["copywriting"]},
        ]}}), encoding="utf-8")

        eng = PipelineEngine(data_dir=data_dir, pipeline_file=str(pipeline_file))
        config = DomainConfig(Path("domains/travel"))
        loader = SkillLoader(config)
        selector = ProviderSelector()
        logger = DecisionLogger(data_dir, "e2e_test")

        eng.register_handler("topic", TopicAgent(loader, selector, logger).execute)
        eng.register_handler("highlight_selection", HighlightAgent(loader, selector, logger).execute)
        eng.register_handler("copywriting", CopywritingAgent(loader, selector, logger).execute)
        eng.register_handler("storyboard", StoryboardAgent(loader, selector, logger).execute)
        eng.register_handler("title", TitleAgent(loader, selector, logger).execute)

        yield eng, data_dir


@pytest.mark.asyncio
async def test_e2e_full_auto_pipeline(e2e_setup):
    """全自动模式：5个阶段连续执行完成"""
    eng, data_dir = e2e_setup
    state = ProjectState(project_id="e2e_test", domain="travel", approval_mode="full_auto")

    await eng.run(state)

    assert state.is_stage_completed("topic")
    assert state.is_stage_completed("highlight_selection")
    assert state.is_stage_completed("copywriting")
    assert state.is_stage_completed("storyboard")
    assert state.is_stage_completed("title")

    topic_output = state.get_stage_output("topic")
    assert topic_output["directions"][0]["name"] == "敦煌探秘"

    cw_output = state.get_stage_output("copywriting")
    assert cw_output["paragraphs"][0]["highlight_ref"] == "mystery_hook"

    sb_output = state.get_stage_output("storyboard")
    assert sb_output["segments"][0]["subtitle_words"][0]["word"] == "你"

    logs = DecisionLogger(data_dir, "e2e_test").get_all()
    assert len(logs) == 5


@pytest.mark.asyncio
async def test_e2e_decision_log_audit_trail(e2e_setup):
    """决策审计日志完整可追溯"""
    eng, data_dir = e2e_setup
    state = ProjectState(project_id="audit_test", approval_mode="full_auto")
    await eng.run(state)

    logs = DecisionLogger(data_dir, "audit_test").get_all()
    for log in logs:
        assert "stage" in log
        assert "provider" in log
        assert "confidence" in log


class TestM22Migration:
    def test_migrate_voices(self):
        from src.tools.migration import migrate_tts_voices
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "voices.json"
            src.write_text('{"magnetic_male": {"name": "磁性男声", "edge_tts_voice": "zh-CN-YunxiNeural"}}', encoding="utf-8")
            tgt = Path(tmp) / "target" / "voices.json"
            assert migrate_tts_voices(src, tgt) == 1
            assert tgt.exists()

    def test_migrate_highlights(self):
        from src.tools.migration import migrate_highlights
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "highlights.json"
            src.write_text('[{"id": "mystery_hook", "name": "悬念式开场"}]', encoding="utf-8")
            tgt = Path(tmp) / "target" / "highlights.json"
            assert migrate_highlights(src, tgt) == 1

    def test_migrate_missing_source(self):
        from src.tools.migration import migrate_tts_voices
        assert migrate_tts_voices("/nonexistent", "/tmp/out.json") == 0


class TestM24Docker:
    def test_dockerfile_exists(self):
        assert Path("Dockerfile").exists()

    def test_docker_compose_exists(self):
        assert Path("docker-compose.yml").exists()
