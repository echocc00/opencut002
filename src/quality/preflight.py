"""前置校验 - 检查阶段输入是否满足要求（含契约校验）"""
from __future__ import annotations

from ..orchestrator.state import ProjectState


# 每个阶段需要的上游输出字段
STAGE_INPUT_SCHEMA: dict[str, dict[str, list[str]]] = {
    "web_research": {"material_analysis": ["images", "destination"]},
    "topic": {"material_analysis": ["images"], "web_research": ["hot_topics"]},
    "highlight_selection": {"topic": ["directions"]},
    "copywriting": {"topic": ["directions"], "highlight_selection": ["options"]},
    "image_matching": {"copywriting": ["paragraphs"], "material_analysis": ["images"]},
    "voice_selection": {"copywriting": ["paragraphs"]},
    "tts": {"copywriting": ["paragraphs"], "voice_selection": ["selected"]},
    "storyboard": {"copywriting": ["paragraphs"], "tts": ["audio_path"]},
    "bgm": {"storyboard": ["segments"]},
    "rhythm": {"storyboard": ["segments"]},
    "title": {"copywriting": ["paragraphs"]},
    "cover": {"storyboard": ["segments"]},
    "fine_cut": {"storyboard": ["segments"], "rhythm": ["segment_timings"]},
    "render": {"storyboard": ["segments"], "tts": ["audio_path"]},
}


def check_prerequisites(state: ProjectState, requires: list[str]) -> tuple[bool, list[str]]:
    """检查前置阶段是否全部完成"""
    issues: list[str] = []
    for req in requires:
        if not state.is_stage_completed(req):
            issues.append(f"前置阶段 {req} 未完成")
    return (len(issues) == 0, issues)


def check_stage_inputs(state: ProjectState, stage_name: str,
                       available_stages: set[str] | None = None) -> tuple[bool, list[str]]:
    """检查上游阶段的输出是否包含必需字段（契约校验）。

    available_stages 为当前管道包含的阶段名集合；不在管道中的上游阶段跳过要求
    （12 阶段冒烟不含 tts，storyboard 不应强求 tts 输出；--full 含 tts 则强求）。
    """
    schema = STAGE_INPUT_SCHEMA.get(stage_name)
    if not schema:
        return (True, [])  # 无契约定义的阶段跳过

    issues: list[str] = []
    for upstream, required_fields in schema.items():
        if available_stages is not None and upstream not in available_stages:
            continue  # 上游阶段不在当前管道中，跳过该要求
        upstream_out = state.get_stage_output(upstream)
        if not upstream_out:
            issues.append(f"上游 {upstream} 无输出数据")
            continue
        for field in required_fields:
            if field not in upstream_out:
                issues.append(f"上游 {upstream} 缺少字段 {field}")
            elif not upstream_out[field]:
                issues.append(f"上游 {upstream} 字段 {field} 为空")

    return (len(issues) == 0, issues)
