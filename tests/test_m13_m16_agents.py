"""M13-M16 验收测试: 全部 AI 阶段 Agent"""
import tempfile
from pathlib import Path
import pytest

from src.agents.topic_agent import TopicAgent
from src.agents.highlight_selection_agent import HighlightAgent
from src.agents.copywriting_agent import CopywritingAgent
from src.agents.voice_selection_agent import VoiceAgent
from src.agents.storyboard_agent import StoryboardAgent
from src.agents.bgm_agent import BGMAgent
from src.agents.rhythm_agent import RhythmAgent
from src.agents.title_agent import TitleAgent
from src.agents.cover_agent import CoverAgent
from src.agents.fine_cut_agent import FineCutAgent
from src.agents.skill_loader import SkillLoader
from src.agents.decision_logger import DecisionLogger
from src.providers.selector import ProviderSelector
from src.providers.provider_registry import Provider, register_provider, clear_registry
from src.config import DomainConfig
from src.orchestrator.state import ProjectState, StageState

# 精确匹配：用输出模板中的唯一JSON key
MOCK_MAP = [
    ('"directions"', '{"directions": [{"name": "敦煌探秘", "hook": "suspense", "psychology": "好奇", "ref_type": "viral", "why_work": "神秘感"}], "selected": -1}'),
    ('"highlight_ids"', '{"options": [{"highlight_ids": ["mystery_hook"], "highlight_names": ["悬念式开场"], "selection_reason": "适合神秘景点", "presentation_style": "悬念式", "expected_effect": "引发好奇"}], "selected": -1}'),
    ('"total_duration"', '{"segments": [{"index": 0, "image": "img1.jpg", "actual_duration": 3.0, "time_start": 0.0, "subtitle": "你见过凌晨四点的敦煌吗", "transition": "crossfade", "subtitle_words": [{"word": "你", "start": 0.0, "end": 0.3}]}], "total_duration": 3.0}'),
    ('"paragraphs"', '{"paragraphs": [{"text": "你见过凌晨四点的敦煌吗", "target_duration": 3.0, "image_hint": "img1.jpg", "highlight_ref": "mystery_hook", "emotion_tone": "悬念"}], "tone": "emotional"}'),
    ('"voice_key"', '{"candidates": [{"voice_key": "magnetic_male", "reason": "适合悬念氛围"}], "selected": "magnetic_male"}'),
    ('"selected_path"', '{"candidates": [{"path": "bgm/cinematic.mp3", "category": "cinematic", "reason": "适合神秘氛围"}], "selected_path": "bgm/cinematic.mp3", "volume": 0.25}'),
    ('"segment_timings"', '{"segment_timings": [{"index": 0, "duration": 3.0, "transition_point": 0.0}], "bgm_start_offset": 0.0}'),
    ('"titles"', '{"titles": ["凌晨四点的敦煌", "99%的人不知道的敦煌"], "selected": -1}'),
    ('"cover_candidates"', '{"cover_candidates": ["frame_0.jpg", "frame_2.jpg"], "selected": -1}'),
    ('"adjustments"', '{"adjustments": [{"index": 0, "duration_delta": 0.0, "transition_duration": 0.4}]}'),
]


@pytest.fixture
def setup():
    clear_registry()
    async def mock_complete(prompt: str, **kw) -> str:
        for key, resp in MOCK_MAP:
            if key in prompt:
                return resp
        return '{}'
    for name in ["deepseek", "doubao", "qwen"]:
        register_provider(name, Provider(name, mock_complete))
    config = DomainConfig(Path("domains/travel"))
    loader = SkillLoader(config)
    selector = ProviderSelector()
    with tempfile.TemporaryDirectory() as tmp:
        logger = DecisionLogger(Path(tmp), "test")
        yield loader, selector, logger


@pytest.mark.asyncio
async def test_topic_agent(setup):
    l, s, lg = setup
    result = await TopicAgent(l, s, lg).execute(ProjectState(project_id="t"), StageState(name="topic"))
    assert "directions" in result["data"]
    assert result["data"]["directions"][0]["name"] == "敦煌探秘"

@pytest.mark.asyncio
async def test_highlight_agent(setup):
    l, s, lg = setup
    st = StageState(name="highlight_selection")
    st.input_data = {"highlights": [{"id": "mystery_hook", "name": "悬念式开场"}]}
    result = await HighlightAgent(l, s, lg).execute(ProjectState(project_id="t"), st)
    assert "options" in result["data"]

@pytest.mark.asyncio
async def test_copywriting_agent(setup):
    l, s, lg = setup
    st = StageState(name="copywriting")
    st.input_data = {"confirmed_highlights": {"highlight_names": ["悬念式开场"], "presentation_style": "悬念式", "expected_effect": "引发好奇"}}
    result = await CopywritingAgent(l, s, lg).execute(ProjectState(project_id="t"), st)
    assert "paragraphs" in result["data"]
    assert result["data"]["paragraphs"][0]["highlight_ref"] == "mystery_hook"

@pytest.mark.asyncio
async def test_voice_agent(setup):
    l, s, lg = setup
    st = StageState(name="voice_selection")
    st.input_data = {"available_voices": {"magnetic_male": {"name": "磁性男声"}}}
    result = await VoiceAgent(l, s, lg).execute(ProjectState(project_id="t"), st)
    assert result["data"]["selected"] == "magnetic_male"

@pytest.mark.asyncio
async def test_storyboard_agent(setup):
    l, s, lg = setup
    result = await StoryboardAgent(l, s, lg).execute(ProjectState(project_id="t"), StageState(name="storyboard"))
    assert "segments" in result["data"]
    assert result["data"]["segments"][0]["subtitle_words"][0]["word"] == "你"

@pytest.mark.asyncio
async def test_bgm_agent(setup):
    l, s, lg = setup
    st = StageState(name="bgm")
    st.input_data = {"available_bgm": ["cinematic.mp3"]}
    result = await BGMAgent(l, s, lg).execute(ProjectState(project_id="t"), st)
    assert result["data"]["volume"] == 0.25

@pytest.mark.asyncio
async def test_rhythm_agent(setup):
    l, s, lg = setup
    result = await RhythmAgent(l, s, lg).execute(ProjectState(project_id="t"), StageState(name="rhythm"))
    assert "segment_timings" in result["data"]

@pytest.mark.asyncio
async def test_title_agent(setup):
    l, s, lg = setup
    result = await TitleAgent(l, s, lg).execute(ProjectState(project_id="t"), StageState(name="title"))
    assert len(result["data"]["titles"]) == 2

@pytest.mark.asyncio
async def test_cover_agent(setup):
    l, s, lg = setup
    result = await CoverAgent(l, s, lg).execute(ProjectState(project_id="t"), StageState(name="cover"))
    assert "cover_candidates" in result["data"]

@pytest.mark.asyncio
async def test_fine_cut_agent(setup):
    l, s, lg = setup
    result = await FineCutAgent(l, s, lg).execute(ProjectState(project_id="t"), StageState(name="fine_cut"))
    assert "adjustments" in result["data"]

def test_all_skill_files_exist():
    skills_dir = Path("domains/travel/skills")
    for name in ["topic","highlight","copywriting","image_matching","voice","tts","storyboard","bgm","rhythm","title","cover","fine_cut","render","web_research"]:
        assert (skills_dir / f"{name}.md").exists(), f"Missing: {name}.md"

def test_all_agents_importable():
    for cls in [TopicAgent,HighlightAgent,CopywritingAgent,VoiceAgent,StoryboardAgent,BGMAgent,RhythmAgent,TitleAgent,CoverAgent,FineCutAgent]:
        assert cls is not None
