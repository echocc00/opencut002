"""P1-P2 修复验证测试"""
import tempfile
from pathlib import Path

import pytest

from src.orchestrator.state import ProjectState, StageStatus


class TestP1_14_RenderDecisionLog:
    """#14: RenderAgent 记录决策日志"""

    def test_render_agent_has_decision_logger(self):
        from src.agents.render_agent import RenderAgent
        assert hasattr(RenderAgent, "decision_logger") or "decision_logger" in RenderAgent.__init__.__code__.co_varnames


class TestP1_15_WhisperXFallback:
    """#15: WhisperX fallback 回填已知文本"""

    def test_transcriber_accepts_known_text(self):
        from src.tools.transcriber import Transcriber
        import inspect
        sig = inspect.signature(Transcriber.transcribe)
        assert "known_text" in sig.parameters

    def test_fallback_fills_words_from_text(self):
        """fallback 模式下用已知文本回填 word 字段"""
        import subprocess, tempfile
        from src.tools.transcriber import Transcriber

        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "test.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                 "-c:a", "pcm_s16le", str(audio)],
                capture_output=True, check=True,
            )
            t = Transcriber(device="cpu")
            result = t.transcribe(audio, known_text="你见过敦煌吗")
            # fallback 模式下应该有词级时间戳
            assert result.method == "fallback"
            assert len(result.words) > 0
            # 至少部分 word 不为空（已知文本回填）
            non_empty = [w for w in result.words if w["word"]]
            assert len(non_empty) > 0
            # full_text 应该包含已知文本
            assert "敦煌" in result.full_text


class TestP1_16_ProviderYAML:
    """#16: Provider 矩阵从 YAML 加载"""

    def test_providers_yaml_exists(self):
        assert Path("config/providers.yaml").exists()

    def test_selector_loads_from_yaml(self):
        from src.providers.selector import ProviderSelector
        selector = ProviderSelector()
        # 从 YAML 加载的权重应该和设计一致
        assert selector.WEIGHTS["task_fit"] == 0.30
        assert selector.WEIGHTS["output_quality"] == 0.20

    def test_selector_works_without_yaml(self):
        """YAML 不存在时用内置默认值"""
        from src.providers.selector import ProviderSelector
        selector = ProviderSelector(config_path="/nonexistent/path.yaml")
        result = selector.select(
            __import__("src.providers.selector", fromlist=["TaskType"]).TaskType.COPYWRITING,
            ["deepseek", "doubao"]
        )
        assert result.winner in ("deepseek", "doubao")

    def test_adding_new_provider_via_yaml(self):
        """通过 YAML 添加新 provider 不需改代码"""
        import yaml
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "providers.yaml"
            config_data = {
                "weights": {"task_fit": 1.0},
                "task_fit_matrix": {"general": {"new_provider": 95, "deepseek": 80}},
                "output_quality": {"new_provider": 90, "deepseek": 85},
                "control": {"new_provider": 85}, "reliability": {"new_provider": 88},
                "cost_efficiency": {"new_provider": 85}, "latency": {"new_provider": 80},
            }
            config_path.write_text(yaml.dump(config_data), encoding="utf-8")
            from src.providers.selector import ProviderSelector, TaskType
            selector = ProviderSelector(config_path=config_path)
            result = selector.select(TaskType.GENERAL, ["new_provider", "deepseek"])
            assert result.winner == "new_provider"


class TestP1_17_PreflightContract:
    """#17: Preflight 契约校验"""

    def test_check_stage_inputs_passes(self):
        from src.quality.preflight import check_stage_inputs
        state = ProjectState(project_id="test")
        state.mark_stage("material_analysis", StageStatus.COMPLETED)
        state.get_stage("material_analysis").output_data = {
            "images": [{"file": "img.jpg"}], "destination": "敦煌"
        }
        ok, issues = check_stage_inputs(state, "web_research")
        assert ok

    def test_check_stage_inputs_fails_missing_field(self):
        from src.quality.preflight import check_stage_inputs
        state = ProjectState(project_id="test")
        state.mark_stage("material_analysis", StageStatus.COMPLETED)
        state.get_stage("material_analysis").output_data = {"images": []}  # 缺 destination
        ok, issues = check_stage_inputs(state, "web_research")
        assert not ok
        assert any("destination" in i for i in issues)

    def test_check_stage_inputs_fails_empty_output(self):
        from src.quality.preflight import check_stage_inputs
        state = ProjectState(project_id="test")
        ok, issues = check_stage_inputs(state, "copywriting")
        assert not ok
        assert any("无输出" in i for i in issues)

    def test_check_stage_inputs_no_schema(self):
        """无契约定义的阶段自动通过"""
        from src.quality.preflight import check_stage_inputs
        state = ProjectState(project_id="test")
        ok, issues = check_stage_inputs(state, "nonexistent_stage")
        assert ok


class TestP1_18_DuckingThreshold:
    """#18: BGM ducking 阈值调整"""

    def test_default_threshold_is_005(self):
        from src.tools.audio_processor import AudioProcessor
        import inspect
        sig = inspect.signature(AudioProcessor.mix_bgm_with_ducking)
        duck_param = sig.parameters.get("duck_threshold")
        assert duck_param.default == 0.05

    def test_release_is_05(self):
        """release 参数应为 0.5"""
        content = Path("src/tools/audio_processor.py").read_text(encoding="utf-8")
        assert "release=0.5" in content


class TestP2_19_NamingConsistency:
    """#19: 命名一致性"""

    def test_highlight_selection_agent_exists(self):
        from src.agents.highlight_selection_agent import HighlightAgent
        assert HighlightAgent is not None

    def test_voice_selection_agent_exists(self):
        from src.agents.voice_selection_agent import VoiceAgent
        assert VoiceAgent is not None


class TestP2_20_ModeBField:
    """#20: 模式 B mode 字段"""

    def test_state_has_mode_field(self):
        state = ProjectState(project_id="test")
        assert hasattr(state, "mode")
        assert state.mode == "material"  # 默认值

    def test_state_has_reference_url(self):
        state = ProjectState(project_id="test")
        assert hasattr(state, "reference_url")
        assert state.reference_url is None  # 默认值

    def test_state_reference_mode(self):
        state = ProjectState(
            project_id="test",
            mode="reference",
            reference_url="https://youtube.com/watch?v=xxx"
        )
        assert state.mode == "reference"
        assert "youtube.com" in state.reference_url
