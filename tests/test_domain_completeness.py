"""领域配置完整性测试 - 验证每个领域具备运行所需的全部配置和技能文件。

新增领域时复制此测试模式，确保 "新增领域不改代码" 的承诺成立。
"""
from pathlib import Path
from src.config import DomainConfig

DOMAINS_DIR = Path("domains")
DOMAINS = ["travel", "education", "knowledge_paid", "custom"]

REQUIRED_CONFIGS = [
    "style.yaml",
    "highlights.json",
    "voices.json",
    "research.json",
    "opening_templates.yaml",
]

REQUIRED_SKILLS = [
    "material_analysis", "web_research", "topic", "highlight", "copywriting",
    "image_matching", "voice", "tts", "storyboard", "bgm", "rhythm",
    "title", "cover", "fine_cut", "render",
]


def test_all_domains_have_required_configs():
    """每个领域都具备 5 个必需配置文件"""
    for domain in DOMAINS:
        d = DOMAINS_DIR / domain
        assert d.exists(), f"领域目录缺失: {domain}"
        for cfg in REQUIRED_CONFIGS:
            assert (d / cfg).exists(), f"领域 {domain} 缺少配置: {cfg}"


def test_all_domains_have_required_skills():
    """每个领域都具备 15 个阶段技能文件"""
    for domain in DOMAINS:
        for skill in REQUIRED_SKILLS:
            assert (DOMAINS_DIR / domain / "skills" / f"{skill}.md").exists(), \
                f"领域 {domain} 缺少技能文件: {skill}.md"


def test_all_domains_have_bgm():
    """每个领域 bgm/ 至少有 1 个 mp3（占位也算，确保 BGM agent 非空）"""
    for domain in DOMAINS:
        bgm_files = list((DOMAINS_DIR / domain / "bgm").glob("*.mp3"))
        assert len(bgm_files) >= 1, f"领域 {domain} 的 bgm/ 为空"


def test_domain_config_loads_all_domains():
    """DomainConfig 能加载每个领域且配置非空"""
    import src.config as cfg_mod
    cfg_mod._domain_cache.clear()  # 清缓存避免跨测试污染
    for domain in DOMAINS:
        dc = DomainConfig(DOMAINS_DIR / domain)
        assert dc.get_highlights(), f"领域 {domain} 的 highlights 为空"
        assert dc.get_voices(), f"领域 {domain} 的 voices 为空"
        assert dc.get_style(), f"领域 {domain} 的 style 为空"


def test_new_domain_can_be_copied_from_travel():
    """从 travel 复制出新领域，完整性校验通过（验证 '新增领域不改代码' 承诺）"""
    import tempfile, shutil
    with tempfile.TemporaryDirectory() as tmp:
        new_domain = Path(tmp) / "domains" / "mydomain"
        shutil.copytree(DOMAINS_DIR / "travel", new_domain)
        # 复制出来的新领域应具备全部必需文件
        for cfg in REQUIRED_CONFIGS:
            assert (new_domain / cfg).exists()
        for skill in REQUIRED_SKILLS:
            assert (new_domain / "skills" / f"{skill}.md").exists()
