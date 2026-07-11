"""真实provider E2E测试 - 验证AI返回的JSON能被正确解析

默认skip，加 --run-integration 才执行：
    pytest tests/test_e2e_real_provider.py --run-integration
"""
import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION"),
    reason="需要 --run-integration 标志和真实API key"
)


@pytest.mark.asyncio
async def test_real_topic_stage():
    """真实调用deepseek跑选题阶段"""
    from src.providers.provider_registry import register_provider, Provider
    from src.agents.topic_agent import TopicAgent
    from src.agents.skill_loader import SkillLoader
    from src.agents.decision_logger import DecisionLogger
    from src.providers.selector import ProviderSelector
    from src.config import DomainConfig
    from src.orchestrator.state import ProjectState, StageState
    from openai import AsyncOpenAI

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        pytest.skip("无DEEPSEEK_API_KEY")

    client = AsyncOpenAI(base_url="https://api.deepseek.com/v1", api_key=api_key)

    async def complete(prompt: str, **kw) -> str:
        resp = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )
        return resp.choices[0].message.content

    register_provider("deepseek", Provider("deepseek", complete))
    register_provider("doubao", Provider("doubao", complete))
    register_provider("qwen", Provider("qwen", complete))

    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        config = DomainConfig(Path("domains/travel"))
        agent = TopicAgent(
            SkillLoader(config), ProviderSelector(), DecisionLogger(Path(tmp), "real")
        )
        state = ProjectState(project_id="real_test", domain="travel")
        stage = StageState(name="topic")
        stage.input_data = {"materials": [{"file": "img1.jpg"}]}

        result = await agent.execute(state, stage)

        assert "directions" in result["data"]
        assert len(result["data"]["directions"]) > 0
        assert result["data"]["directions"][0]["name"]  # 非空
        assert result["confidence"] > 0
