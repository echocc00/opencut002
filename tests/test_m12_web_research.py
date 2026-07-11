"""M12 验收测试: Web 调研阶段"""
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.agents.web_research_agent import WebResearchAgent
from src.agents.skill_loader import SkillLoader
from src.agents.decision_logger import DecisionLogger
from src.providers.selector import ProviderSelector
from src.providers.provider_registry import Provider, register_provider, clear_registry
from src.config import DomainConfig
from src.orchestrator.state import ProjectState, StageState


@pytest.fixture
def setup():
    clear_registry()
    async def mock_complete(prompt: str, **kw) -> str:
        return '{"hot_topics": ["敦煌夜游", "莫高窟特窟"], "angle_suggestions": ["凌晨四点的敦煌"], "avoid_angles": ["敦煌攻略大全"], "differentiation": "从时间维度切入"}'
    register_provider("deepseek", Provider("deepseek", mock_complete))
    register_provider("doubao", Provider("doubao", mock_complete))
    register_provider("qwen", Provider("qwen", mock_complete))

    config = DomainConfig(Path("domains/travel"))
    loader = SkillLoader(config)
    selector = ProviderSelector()
    with tempfile.TemporaryDirectory() as tmp:
        logger = DecisionLogger(Path(tmp), "test")
        agent = WebResearchAgent(loader, selector, logger)
        yield agent, logger


def test_web_research_skill_loaded():
    config = DomainConfig(Path("domains/travel"))
    loader = SkillLoader(config)
    skill = loader.load("web_research")
    assert "trending topics" in skill["purpose"]
    assert len(skill["quality_rules"]) >= 4


def test_web_research_build_prompt():
    config = DomainConfig(Path("domains/travel"))
    loader = SkillLoader(config)
    selector = ProviderSelector()
    with tempfile.TemporaryDirectory() as tmp:
        logger = DecisionLogger(Path(tmp), "test")
        agent = WebResearchAgent(loader, selector, logger)
        prompt = agent._build_prompt(
            skill_context="【技能】",
            upstream_context="",
            user_note="",
            input_data={"destination": "敦煌", "materials": [{"scene": "莫高窟"}],
                        "search_results": [{"query": "敦煌", "text": "敦煌热门"}]},
        )
        assert "敦煌" in prompt
        assert "敦煌热门" in prompt


def test_web_research_parse_output():
    config = DomainConfig(Path("domains/travel"))
    loader = SkillLoader(config)
    selector = ProviderSelector()
    with tempfile.TemporaryDirectory() as tmp:
        logger = DecisionLogger(Path(tmp), "test")
        agent = WebResearchAgent(loader, selector, logger)
        output = agent._parse_output('{"hot_topics": ["敦煌夜游"], "angle_suggestions": ["凌晨"], "avoid_angles": ["攻略"], "differentiation": "时间维度"}')
        assert output["hot_topics"] == ["敦煌夜游"]


def test_web_research_parse_empty():
    config = DomainConfig(Path("domains/travel"))
    loader = SkillLoader(config)
    selector = ProviderSelector()
    with tempfile.TemporaryDirectory() as tmp:
        logger = DecisionLogger(Path(tmp), "test")
        agent = WebResearchAgent(loader, selector, logger)
        output = agent._parse_output("no json")
        assert output["hot_topics"] == []


@pytest.mark.asyncio
async def test_web_research_full_execution(setup):
    """完整执行：mock搜索 -> AI整合 -> 输出简报"""
    agent, logger = setup
    state = ProjectState(project_id="test", domain="travel")
    state.mark_stage("material_analysis", "completed")
    state.get_stage("material_analysis").output_data = {
        "destination": "敦煌",
        "images": [{"scene": "莫高窟", "emotion": "神秘"}],
    }
    stage = StageState(name="web_research")

    # mock batch_search 避免网络请求
    mock_results = [{"query": "敦煌旅游", "text": "敦煌莫高窟是热门景点"}]
    with patch("src.agents.web_research_agent.batch_search", new_callable=AsyncMock, return_value=mock_results):
        result = await agent.execute(state, stage)

    assert "data" in result
    assert "confidence" in result
    data = result["data"]
    assert "hot_topics" in data
    assert len(data["hot_topics"]) == 2
    assert "raw_results" in data
    assert data["raw_results"] == mock_results
