"""M01 验收测试: 项目脚手架 + 配置系统"""
from pathlib import Path
from src.config import Settings, get_settings


def test_settings_default_paths():
    """配置系统能加载默认路径"""
    s = Settings()
    assert s.data_dir is not None
    assert s.domains_dir is not None
    assert s.remotion_dir is not None


def test_settings_env_prefix():
    """环境变量前缀正确"""
    assert Settings.model_config.get("env_prefix") == "OPENCUT_"


def test_directory_structure_exists():
    """项目目录结构与设计文档一致"""
    base = Path(__file__).parent.parent
    expected_dirs = [
        "src/orchestrator",
        "src/agents",
        "src/tools",
        "src/quality",
        "src/providers",
        "src/observability",
        "src/api",
        "domains/travel",
        "domains/education",
        "domains/knowledge_paid",
        "domains/custom",
        "remotion/src",
        "tests",
        "pipelines",
    ]
    for d in expected_dirs:
        assert (base / d).is_dir(), f"目录不存在: {d}"


def test_config_importable():
    """config 模块可正常导入"""
    s = get_settings()
    assert s.ffmpeg_path == "ffmpeg"
    assert s.remotion_fps == 30
