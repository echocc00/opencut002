"""真实 provider E2E 冒烟测试 - 用真实 minimax 跑选题阶段，验证 AI 返回的 JSON 能被正确解析。

默认 skip，加 RUN_INTEGRATION=1 才执行：
    RUN_INTEGRATION=1 pytest tests/test_e2e_real_provider.py -s

需 .env 配置 MINIMAX_API_KEY（真实 key，非占位符）。
"""
import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION"),
    reason="需要 RUN_INTEGRATION=1 标志和真实 MINIMAX_API_KEY",
)


@pytest.mark.asyncio
async def test_real_minimax_topic_stage():
    """真实 minimax 跑选题阶段，验证 ProviderResponse + JSON 解析 + decision_log"""
    from src.providers.provider_registry import auto_register_from_env, list_providers
    from src.agents.topic_agent import TopicAgent
    from src.agents.skill_loader import SkillLoader
    from src.agents.decision_logger import DecisionLogger
    from src.providers.selector import ProviderSelector
    from src.config import DomainConfig
    from src.orchestrator.state import ProjectState, StageState

    registered = auto_register_from_env()
    if "minimax" not in registered:
        pytest.skip("无真实 MINIMAX_API_KEY（.env 中需配置非占位符 key）")

    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        config = DomainConfig(Path("domains/travel"))
        agent = TopicAgent(
            SkillLoader(config), ProviderSelector(), DecisionLogger(Path(tmp), "real_smoke")
        )
        state = ProjectState(project_id="real_smoke", domain="travel", approval_mode="full_auto")
        stage = StageState(name="topic")
        stage.input_data = {"materials": [{"file": "img1.jpg", "filename": "img1.jpg"}]}

        result = await agent.execute(state, stage)

        # 验证 AI 返回合法 JSON 被解析
        assert "directions" in result["data"]
        assert len(result["data"]["directions"]) > 0
        assert result["data"]["directions"][0]["name"]
        assert result["confidence"] > 0

        # 验证 decision_log 含 R10 新字段（token/model/cost）
        logs = DecisionLogger(Path(tmp), "real_smoke").get_all()
        assert logs, "decision_log 应有记录"
        entry = logs[-1]
        assert entry.get("provider") == "minimax"
        assert entry.get("model")  # model 非空
        assert entry.get("input_tokens", 0) > 0  # 真实调用有 token 用量
        assert entry.get("cost", 0) > 0  # 真实调用有成本
        assert entry.get("prompt_skill_file") == "domains/travel/skills/topic.md"
