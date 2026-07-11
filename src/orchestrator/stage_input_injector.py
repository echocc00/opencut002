"""阶段输入注入 - 从领域配置/上游输出填充各阶段的 input_data

与 preflight.STAGE_INPUT_SCHEMA 对齐：preflight 定义"需要哪些上游字段"，
injector 定义"如何获取这些字段"。单一真理来源，避免注入规则与契约不同步。
"""
from __future__ import annotations

from ..config import get_domain_config
from ..orchestrator.state import ProjectState, StageState


def inject_stage_input(state: ProjectState, stage: StageState) -> None:
    """为特定阶段注入 input_data（仅当尚未存在时填充）"""
    name = stage.name

    if name == "highlight_selection" and not stage.input_data.get("highlights"):
        domain_cfg = get_domain_config(state.domain)
        stage.input_data["highlights"] = domain_cfg.get_highlights()

    elif name == "storyboard" and "tts_total_duration" not in stage.input_data:
        tts_output = state.get_stage_output("tts")
        if tts_output:
            words = tts_output.get("word_timestamps", [])
            if words:
                stage.input_data["tts_total_duration"] = max(w.get("end", 0) for w in words)

    elif name == "copywriting" and not stage.input_data.get("confirmed_highlights"):
        hl_output = state.get_stage_output("highlight_selection")
        if hl_output and hl_output.get("selected", -1) >= 0:
            opts = hl_output.get("options", [])
            sel = hl_output["selected"]
            if 0 <= sel < len(opts):
                stage.input_data["confirmed_highlights"] = opts[sel]

    elif name == "voice_selection" and not stage.input_data.get("available_voices"):
        domain_cfg = get_domain_config(state.domain)
        stage.input_data["available_voices"] = domain_cfg.get_voices()

    elif name == "bgm" and not stage.input_data.get("available_bgm"):
        domain_cfg = get_domain_config(state.domain)
        bgm_dir = domain_cfg.dir / "bgm"
        if bgm_dir.exists():
            stage.input_data["available_bgm"] = [f.name for f in bgm_dir.glob("*.mp3")]
        else:
            stage.input_data["available_bgm"] = []
