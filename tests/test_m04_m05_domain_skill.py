"""M04+M05 验收测试: 领域配置 + 技能文件加载器"""
from pathlib import Path

from src.config import DomainConfig, get_domain_config
from src.agents.skill_loader import SkillLoader


def test_domain_config_loads_travel():
    """DomainConfig 能加载 travel 领域全部配置"""
    config = DomainConfig(Path("domains/travel"))
    assert config.name == "travel"
    assert config.style["domain"] == "travel"
    assert config.style["display_name"] == "文旅短视频"
    assert len(config.highlights) > 0
    assert len(config.voices) >= 8
    assert "search_queries" in config.research
    assert "templates" in config.opening_templates


def test_domain_config_get_highlights():
    """亮点库数据正确"""
    config = DomainConfig(Path("domains/travel"))
    highlights = config.get_highlights()
    assert len(highlights) >= 6
    assert any(h["id"] == "mystery_hook" for h in highlights)


def test_domain_config_get_voices():
    """音色配置正确"""
    config = DomainConfig(Path("domains/travel"))
    voices = config.get_voices()
    assert "magnetic_male" in voices
    assert "edge_tts_voice" in voices["magnetic_male"]


def test_domain_config_get_style():
    """风格配置正确"""
    config = DomainConfig(Path("domains/travel"))
    style = config.get_style()
    assert style["copywriting"]["tone"] == "emotional"
    assert style["pacing"]["default_duration"] == 45


def test_domain_config_get_skill():
    """技能文件加载正确"""
    config = DomainConfig(Path("domains/travel"))
    skill = config.get_skill("copywriting")
    assert "Copywriting Stage Skill" in skill
    assert "## Quality Rules" in skill


def test_domain_config_missing_skill():
    """不存在的技能文件返回空字符串"""
    config = DomainConfig(Path("domains/travel"))
    assert config.get_skill("nonexistent") == ""


def test_skill_loader_parses_copywriting():
    """SkillLoader 能解析 Markdown 结构"""
    config = DomainConfig(Path("domains/travel"))
    loader = SkillLoader(config)
    skill = loader.load("copywriting")

    assert skill["purpose"] != ""
    assert len(skill["quality_rules"]) >= 5
    assert len(skill["anti_patterns"]) >= 4
    assert len(skill["output_contract"]) >= 5
    assert skill["guidance"] != ""


def test_skill_loader_build_prompt_context():
    """build_prompt_context 返回完整的 prompt 上下文"""
    config = DomainConfig(Path("domains/travel"))
    loader = SkillLoader(config)
    context = loader.build_prompt_context("copywriting")

    assert "【阶段目标】" in context
    assert "【输出要求】" in context
    assert "【质量规则 - 必须遵守】" in context
    assert "【禁止事项】" in context
    assert "【领域指导】" in context


def test_skill_loader_topic():
    """选题技能文件解析正确"""
    config = DomainConfig(Path("domains/travel"))
    loader = SkillLoader(config)
    skill = loader.load("topic")
    assert "2-3 topic directions" in skill["purpose"]
    assert len(skill["quality_rules"]) >= 4


def test_skill_loader_storyboard():
    """分镜技能文件解析正确"""
    config = DomainConfig(Path("domains/travel"))
    loader = SkillLoader(config)
    skill = loader.load("storyboard")
    assert "storyboard segments" in skill["purpose"]
    assert len(skill["output_contract"]) >= 5


def test_skill_loader_nonexistent():
    """不存在的技能文件返回空结构"""
    config = DomainConfig(Path("domains/travel"))
    loader = SkillLoader(config)
    skill = loader.load("nonexistent")
    assert skill["content"] == ""
    assert skill["quality_rules"] == []
    assert loader.build_prompt_context("nonexistent") == ""
