"""阶段间数据契约 - 每个阶段的输入输出格式定义"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class MaterialAnalysisOutput(BaseModel):
    images: list[dict[str, Any]] = Field(default_factory=list)
    destination: str = ""
    scene_types: list[str] = Field(default_factory=list)


class WebResearchOutput(BaseModel):
    hot_topics: list[str] = Field(default_factory=list)
    angle_suggestions: list[str] = Field(default_factory=list)
    avoid_angles: list[str] = Field(default_factory=list)
    differentiation: str = ""
    raw_results: list[dict[str, Any]] = Field(default_factory=list)


class TopicDirection(BaseModel):
    name: str = ""
    hook: str = ""
    psychology: str = ""
    ref_type: str = ""
    why_work: str = ""


class TopicOutput(BaseModel):
    directions: list[TopicDirection] = Field(default_factory=list)
    selected: int = -1


class HighlightOption(BaseModel):
    highlight_ids: list[str] = Field(default_factory=list)
    highlight_names: list[str] = Field(default_factory=list)
    selection_reason: str = ""
    presentation_style: str = ""
    expected_effect: str = ""


class HighlightOutput(BaseModel):
    options: list[HighlightOption] = Field(default_factory=list)
    selected: int = -1


class CopywritingParagraph(BaseModel):
    text: str = ""
    target_duration: float = 3.5
    image_hint: str = ""
    highlight_ref: str = ""
    emotion_tone: str = ""


class CopywritingOutput(BaseModel):
    paragraphs: list[CopywritingParagraph] = Field(default_factory=list)
    tone: str = ""


class StoryboardSegment(BaseModel):
    index: int = 0
    image: str = ""
    image_b: str = ""
    ab_split: bool = False
    audio: str = ""
    actual_duration: float = 0.0
    time_start: float = 0.0
    subtitle: str = ""
    transition: str = "crossfade"
    subtitle_words: list[dict[str, Any]] = Field(default_factory=list)


class StoryboardOutput(BaseModel):
    segments: list[StoryboardSegment] = Field(default_factory=list)
    total_duration: float = 0.0


class VoiceOutput(BaseModel):
    selected_voice: str = ""
    voice_name: str = ""
    audio_path: str = ""
    word_timestamps: list[dict[str, Any]] = Field(default_factory=list)


class BGMOutput(BaseModel):
    bgm_path: str = ""
    bgm_category: str = ""
    volume: float = 0.25


class RhythmOutput(BaseModel):
    segment_timings: list[dict[str, Any]] = Field(default_factory=list)
    bgm_start_offset: float = 0.0


class TitleOutput(BaseModel):
    titles: list[str] = Field(default_factory=list)
    selected: int = -1


class CoverOutput(BaseModel):
    cover_candidates: list[str] = Field(default_factory=list)
    selected: int = -1


class RenderOutput(BaseModel):
    video_path: str = ""
    duration: float = 0.0
    quality_report: Optional[dict[str, Any]] = None


# 契约注册表 - 阶段名 -> 输出模型
OUTPUT_CONTRACTS: dict[str, type[BaseModel]] = {
    "material_analysis": MaterialAnalysisOutput,
    "web_research": WebResearchOutput,
    "topic": TopicOutput,
    "highlight_selection": HighlightOutput,
    "copywriting": CopywritingOutput,
    "storyboard": StoryboardOutput,
    "voice_selection": VoiceOutput,
    "tts": VoiceOutput,
    "bgm": BGMOutput,
    "rhythm": RhythmOutput,
    "title": TitleOutput,
    "cover": CoverOutput,
    "render": RenderOutput,
}
