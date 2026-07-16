"""成本预算闸测试（v0.6.2）。"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.orchestrator.cost_tracker import CostTracker, BudgetExceeded
from src.orchestrator.state import ProjectState


class TestCostTracker:
    def test_budget_zero_unlimited(self):
        s = ProjectState(project_id="t")  # budget_usd=0 默认
        assert CostTracker.check_budget(s, estimated_usd=999.0) is True

    def test_within_limit(self):
        s = ProjectState(project_id="t", budget_usd=1.0, cost_total=0.4)
        assert CostTracker.check_budget(s, estimated_usd=0.2) is True

    def test_exceeded_raises(self):
        s = ProjectState(project_id="t", budget_usd=0.5, cost_total=0.4)
        with pytest.raises(BudgetExceeded) as ei:
            CostTracker.check_budget(s, estimated_usd=0.2, stage_name="tts")
        assert "tts" in str(ei.value)
        assert ei.value.budget == 0.5

    def test_exceeded_without_estimate(self):
        """estimated=0：已花超预算即 raise（post-hoc 闸）。"""
        s = ProjectState(project_id="t", budget_usd=0.3, cost_total=0.4)
        with pytest.raises(BudgetExceeded):
            CostTracker.check_budget(s, stage_name="render")


class TestStateBudgetField:
    def test_budget_usd_default_zero(self):
        s = ProjectState(project_id="t")
        assert s.budget_usd == 0.0
        assert s.schema_version == 3

    def test_budget_usd_set(self):
        s = ProjectState(project_id="t", budget_usd=2.5)
        assert s.budget_usd == 2.5


class TestV2ToV3Migration:
    def test_v2_to_v3_adds_budget_usd(self):
        from src.orchestrator.state_migrator import migrate_state, CURRENT_VERSION
        assert CURRENT_VERSION == 3
        v2 = {"project_id": "p1", "schema_version": 2}
        data, versions = migrate_state(v2)
        assert data["schema_version"] == 3
        assert data["budget_usd"] == 0.0
        assert versions == [3]

    def test_v2_to_v3_does_not_overwrite(self):
        from src.orchestrator.state_migrator import migrate_state
        v2 = {"project_id": "p1", "schema_version": 2, "budget_usd": 1.5}
        data, _ = migrate_state(v2)
        assert data["budget_usd"] == 1.5  # 不覆盖

    def test_v1_migrates_through_v2_to_v3(self):
        from src.orchestrator.state_migrator import migrate_state
        v1 = {"project_id": "p1"}  # 无 schema_version = v1
        data, versions = migrate_state(v1)
        assert data["schema_version"] == 3
        assert data["budget_usd"] == 0.0
        assert versions == [2, 3]

    def test_load_migrates_v2_state_file(self, tmp_path):
        """ProjectState.load 自动迁 v2 -> v3。"""
        projects = tmp_path / "projects" / "p1"
        projects.mkdir(parents=True)
        (projects / "state.json").write_text(
            json.dumps({"project_id": "p1", "schema_version": 2, "cost_total": 0.1}),
            encoding="utf-8")
        state = ProjectState.load(tmp_path, "p1")
        assert state is not None
        assert state.schema_version == 3
        assert state.budget_usd == 0.0
        assert state.cost_total == 0.1  # 保留


class TestCalcTtsCost:
    def test_zero_rate_placeholder(self):
        """provider_pricing.yaml 里 minimax_tts.per_1k_chars=0.0 占位 -> 成本 0。"""
        from src.providers.pricing import calc_tts_cost
        assert calc_tts_cost(10000) == 0.0

    def test_with_rate(self, tmp_path, monkeypatch):
        """自定义 rate 文件算成本。"""
        # 用临时 pricing 文件
        from src.providers import pricing
        pricing_file = tmp_path / "p.yaml"
        pricing_file.write_text("minimax_tts:\n  per_1k_chars: 0.1\n", encoding="utf-8")
        monkeypatch.setattr(pricing, "_PRICING", None)
        with patch.object(pricing, "load_pricing", return_value={"minimax_tts": {"per_1k_chars": 0.1}}):
            assert pricing.calc_tts_cost(2500) == 0.25

    def test_unknown_provider_zero(self):
        from src.providers.pricing import calc_tts_cost
        assert calc_tts_cost(1000, provider="nope") == 0.0


class TestTTSAgentCostTracking:
    """TTS 成本纳入 state_updates（修 TTS override 基类不返 state_updates 的 bug）。"""

    @pytest.mark.asyncio
    async def test_tts_returns_state_updates_with_cost(self, tmp_path, monkeypatch):
        from src.agents.tts_agent import TTSAgent
        from src.orchestrator.state import ProjectState, StageState

        # 构造 state：copywriting 输出有 1 段
        state = ProjectState(project_id="tts_test", domain="education")
        state.stages["copywriting"] = StageState(name="copywriting")
        state.stages["copywriting"].output_data = {
            "paragraphs": [{"text": "你好世界测试", "emotion_tone": ""}]}
        state.stages["copywriting"].status = "completed"
        stage = StageState(name="tts")

        agent = TTSAgent(skill_loader=Mock(), provider_selector=Mock(), decision_logger=Mock())

        # mock 掉 TTS 生成 + 时长探测 + 拼接 + 对齐
        async def fake_tts(*a, **kw):
            out = Path(a[2])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"mp3")
            return str(out)
        monkeypatch.setattr("src.agents.tts_agent.generate_tts", fake_tts)
        monkeypatch.setattr("src.agents.tts_agent._probe_duration", lambda p: 2.0)
        monkeypatch.setattr("src.agents.tts_agent._concat_audio",
                            lambda segs, out: (Path(out).parent.mkdir(parents=True, exist_ok=True), Path(out).write_bytes(b"mp3")))
        monkeypatch.setattr("src.agents.tts_agent._trim_silence_enabled", lambda: False)
        monkeypatch.setattr("src.agents.tts_agent._forced_align_enabled", lambda: False)
        # copywriting stage output 读取走 state.get_stage_output
        # voice_selection 留空走默认 voice

        result = await agent.execute(state, stage)

        assert "state_updates" in result, "TTS 应返回 state_updates（v0.6.2 修复）"
        assert "cost_total" in result["state_updates"]
        # minimax_tts rate=0 占位 -> 加 0；但 state_updates 必须存在
        assert result["state_updates"]["cost_total"] == state.cost_total
