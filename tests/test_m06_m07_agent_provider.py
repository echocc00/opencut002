"""M06+M07 验收测试: Agent 框架 + Provider 评分"""
import tempfile
from pathlib import Path

import pytest

from src.providers.selector import ProviderSelector, TaskType, SelectionResult
from src.providers.provider_registry import Provider, register_provider, get_provider, clear_registry
from src.agents.decision_logger import DecisionLogger
from src.agents.skill_loader import SkillLoader
from src.agents.base_agent import BaseStageAgent
from src.config import DomainConfig
from src.orchestrator.state import ProjectState, StageState


# ========== M07: Provider 评分 ==========

def test_provider_selector_scores_all_dimensions():
    """7 维度评分完整"""
    selector = ProviderSelector()
    result = selector.select(TaskType.COPYWRITING, ["doubao", "deepseek", "qwen"])
    assert len(result.scores) == 3
    for score in result.scores:
        assert len(score.dimensions) == 7
        assert score.total_score > 0


def test_provider_selector_picks_best():
    """选出总分最高的 provider"""
    selector = ProviderSelector()
    result = selector.select(TaskType.COPYWRITING, ["doubao", "deepseek", "qwen"])
    # deepseek 在 copywriting 上 task_fit=90, output_quality=85，应该胜出
    assert result.winner == "deepseek"
    assert result.total_score > 80


def test_provider_selector_reasoning():
    """选择理由包含 provider 名称和分数"""
    selector = ProviderSelector()
    result = selector.select(TaskType.TOPIC_GENERATION, ["doubao", "deepseek"])
    assert "doubao" in result.reasoning or "deepseek" in result.reasoning
    assert "分" in result.reasoning


def test_provider_selector_continuity_bonus():
    """与前一个 provider 一致时 continuity 加分"""
    selector = ProviderSelector()
    r1 = selector.select(TaskType.COPYWRITING, ["doubao", "deepseek"], previous_provider="deepseek")
    r2 = selector.select(TaskType.COPYWRITING, ["doubao", "deepseek"], previous_provider="doubao")
    # deepseek 的 continuity 在 r1 中应该更高
    ds_r1 = next(s for s in r1.scores if s.provider_name == "deepseek")
    ds_r2 = next(s for s in r2.scores if s.provider_name == "deepseek")
    assert ds_r1.dimensions["continuity"] == 100
    assert ds_r2.dimensions["continuity"] == 50


def test_provider_selector_logs_decision():
    """决策日志写入 JSONL 文件"""
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "log.jsonl"
        selector = ProviderSelector()
        selector.select(TaskType.TOPIC_GENERATION, ["doubao", "deepseek"], log_path=log_path)
        assert log_path.exists()
        import json
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert "winner" in entry
        assert "reasoning" in entry
        assert "all_scores" in entry


# ========== M06: Agent 框架 ==========

def test_decision_logger_writes_and_reads():
    """决策日志写入和读取"""
    with tempfile.TemporaryDirectory() as tmp:
        logger = DecisionLogger(Path(tmp), "test_proj")
        logger.log(stage="topic", provider="deepseek", confidence=85)
        logger.log(stage="copywriting", provider="doubao", confidence=70)

        all_logs = logger.get_all()
        assert len(all_logs) == 2
        assert all_logs[0]["stage"] == "topic"
        assert all_logs[1]["stage"] == "copywriting"

        topic_logs = logger.get_by_stage("topic")
        assert len(topic_logs) == 1
        assert topic_logs[0]["provider"] == "deepseek"


@pytest.mark.asyncio
async def test_base_stage_agent_with_mock_provider():
    """BaseStageAgent 能读取技能文件、调用 AI（mock）、解析输出"""
    clear_registry()

    async def mock_complete(prompt: str, **kwargs) -> str:
        return '{"directions": [{"name": "敦煌探秘", "hook": "suspense"}], "selected": -1}'

    register_provider("deepseek", Provider("deepseek", mock_complete))
    register_provider("doubao", Provider("doubao", mock_complete))
    register_provider("qwen", Provider("qwen", mock_complete))

    with tempfile.TemporaryDirectory() as tmp:
        config = DomainConfig(Path("domains/travel"))
        skill_loader = SkillLoader(config)
        selector = ProviderSelector()
        logger = DecisionLogger(Path(tmp), "test_proj")

        class TestTopicAgent(BaseStageAgent):
            def get_task_type(self):
                return TaskType.TOPIC_GENERATION

            def _build_prompt(self, skill_context, upstream_context, user_note, input_data):
                return f"{skill_context}\n\n{upstream_context}\n\n{user_note}\n\n生成选题"

            def _parse_output(self, response):
                return self._extract_json(response)

        agent = TestTopicAgent(skill_loader, selector, logger)
        state = ProjectState(project_id="test_proj")
        stage = StageState(name="topic")
        stage.input_data = {"materials": ["img1.jpg"]}

        result = await agent.execute(state, stage)

        assert "data" in result
        assert "confidence" in result
        assert "directions" in result["data"]
        assert result["data"]["directions"][0]["name"] == "敦煌探秘"
        assert result["confidence"] > 0

        # 决策日志已记录
        logs = logger.get_all()
        assert len(logs) == 1
        assert logs[0]["stage"] == "topic"
        assert logs[0]["provider"] in ("deepseek", "doubao", "qwen")
        assert "confidence" in logs[0]


def test_base_stage_agent_confidence_scoring():
    """置信度评分：空输出低分，完整输出高分"""
    config = DomainConfig(Path("domains/travel"))
    skill_loader = SkillLoader(config)
    selector = ProviderSelector()

    with tempfile.TemporaryDirectory() as tmp:
        logger = DecisionLogger(Path(tmp), "test")

        class DummyAgent(BaseStageAgent):
            def get_task_type(self): return TaskType.GENERAL
            def _build_prompt(self, *a): return ""
            def _parse_output(self, r): return {}

        agent = DummyAgent(skill_loader, selector, logger)
        from src.agents.confidence_scorer import calculate_confidence
        assert calculate_confidence({}) == 20.0
        assert calculate_confidence({"a": "b", "c": "d", "e": "f"}) >= 50.0
