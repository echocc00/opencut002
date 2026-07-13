"""C0.7 稳定性增强测试：AI 调用退避重试 + xxx_plan 展平 + 质量关卡阈值可配置"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.base_agent import BaseStageAgent
from src.quality.slideshow_scorer import score_storyboard


class _StubAgent(BaseStageAgent):
    """绕过重型 __init__ 的测试桩，仅测 _call_ai / _flatten_plan_namespace"""
    def __init__(self) -> None:
        pass

    def get_task_type(self): ...
    def _build_prompt(self, *a): ...
    def _parse_output(self, r): ...


# ========== _flatten_plan_namespace ==========

def test_flatten_plan_namespace_unwraps_wrapped_output():
    """AI 把输出包在 rhythm_plan 里 -> 展平到顶层"""
    agent = _StubAgent()
    data = {"rhythm_plan": {"segment_timings": [{"i": 0}], "bgm_start_offset": 1.5}}
    out = agent._flatten_plan_namespace(data)
    assert out["segment_timings"] == [{"i": 0}]
    assert out["bgm_start_offset"] == 1.5


def test_flatten_plan_namespace_preserves_existing_top_level():
    """顶层已有同名字段时 setdefault 不覆盖"""
    agent = _StubAgent()
    data = {"segment_timings": [{"top": True}], "rhythm_plan": {"segment_timings": [{"nested": True}]}}
    out = agent._flatten_plan_namespace(data)
    assert out["segment_timings"] == [{"top": True}]


def test_flatten_plan_namespace_no_op_on_plain_output():
    """正常输出（无 xxx_plan 包裹）-> 不变"""
    agent = _StubAgent()
    data = {"paragraphs": [{"text": "hi"}], "tone": "neutral"}
    out = agent._flatten_plan_namespace(data)
    assert out == data


def test_flatten_plan_namespace_non_dict_passthrough():
    agent = _StubAgent()
    assert agent._flatten_plan_namespace("not a dict") == "not a dict"
    assert agent._flatten_plan_namespace(None) is None


# ========== _call_ai 退避重试 ==========

@pytest.mark.asyncio
@patch("src.agents.base_agent.asyncio.sleep", new_callable=AsyncMock)
async def test_call_ai_retries_then_succeeds(mock_sleep):
    """前 2 次失败、第 3 次成功 -> 返回结果，共 3 次尝试"""
    agent = _StubAgent()
    provider = MagicMock()
    response = MagicMock(text='{"ok": true}')
    provider.complete = AsyncMock(side_effect=[RuntimeError("限流"), RuntimeError("网络"), response])
    with patch("src.providers.provider_registry.get_provider", return_value=provider):
        result = await agent._call_ai("minimax", "prompt")
    assert result is response
    assert provider.complete.await_count == 3
    assert mock_sleep.await_count == 2  # 两次重试间各 sleep 一次


@pytest.mark.asyncio
@patch("src.agents.base_agent.asyncio.sleep", new_callable=AsyncMock)
async def test_call_ai_raises_after_max_attempts(mock_sleep):
    """3 次全失败 -> 抛最后异常"""
    agent = _StubAgent()
    provider = MagicMock()
    provider.complete = AsyncMock(side_effect=RuntimeError("持续失败"))
    with patch("src.providers.provider_registry.get_provider", return_value=provider):
        with pytest.raises(RuntimeError, match="持续失败"):
            await agent._call_ai("minimax", "prompt")
    assert provider.complete.await_count == 3
    assert mock_sleep.await_count == 2


@pytest.mark.asyncio
async def test_call_ai_succeeds_first_try():
    """首次成功 -> 不重试"""
    agent = _StubAgent()
    provider = MagicMock()
    response = MagicMock(text='{"ok": true}')
    provider.complete = AsyncMock(return_value=response)
    with patch("src.providers.provider_registry.get_provider", return_value=provider):
        result = await agent._call_ai("minimax", "prompt")
    assert result is response
    assert provider.complete.await_count == 1


# ========== slideshow 阈值可配置 ==========

def test_slideshow_default_threshold_blocks_at_70():
    """默认 high=70 -> 无图+长字幕+静态+长时长的高风险分镜被阻断"""
    segments = [
        {"image": "", "actual_duration": 6.0, "ab_split": False, "subtitle": "字" * 60},
        {"image": "", "actual_duration": 6.0, "ab_split": False, "subtitle": "字" * 60},
        {"image": "", "actual_duration": 6.0, "ab_split": False, "subtitle": "字" * 60},
        {"image": "", "actual_duration": 6.0, "ab_split": False, "subtitle": "字" * 60},
    ]
    score = score_storyboard(segments)
    assert score.total_score >= 70
    assert not score.passed
    assert score.risk_level in ("high", "critical")


def test_slideshow_relaxed_threshold_allows_high_risk():
    """放宽 high=95 -> 同样高风险分镜不再阻断"""
    segments = [
        {"image": "", "actual_duration": 6.0, "ab_split": False, "subtitle": "字" * 60},
        {"image": "", "actual_duration": 6.0, "ab_split": False, "subtitle": "字" * 60},
        {"image": "", "actual_duration": 6.0, "ab_split": False, "subtitle": "字" * 60},
        {"image": "", "actual_duration": 6.0, "ab_split": False, "subtitle": "字" * 60},
    ]
    score = score_storyboard(segments, thresholds={"high": 95, "critical": 99})
    assert score.passed
    assert score.risk_level in ("medium", "low")


def test_slideshow_partial_threshold_override_merges_with_defaults():
    """只覆盖 high，其余保持默认"""
    segments = [{"image": f"img{i}.jpg", "actual_duration": 3.0, "ab_split": True, "subtitle": "s"} for i in range(4)]
    score = score_storyboard(segments, thresholds={"high": 80})
    assert score.passed
