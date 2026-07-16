"""领域配置 TTL 缓存测试（v0.6.1）。"""
from __future__ import annotations

import pytest

from src import config


@pytest.fixture(autouse=True)
def _reset_caches(monkeypatch):
    """每测试清 settings + domain 缓存，防污染。"""
    cfg = config
    cfg._settings = None
    cfg.clear_domain_cache()
    yield
    cfg._settings = None
    cfg.clear_domain_cache()


class TestDomainConfigCache:
    def test_caches_instance(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENCUT_DOMAINS_DIR", str(tmp_path))
        (tmp_path / "education").mkdir()
        (tmp_path / "education" / "style.yaml").write_text("visual:\n  active_color: red", encoding="utf-8")
        c1 = config.get_domain_config("education")
        c2 = config.get_domain_config("education")
        assert c1 is c2  # 同实例（缓存命中）

    def test_ttl_zero_reloads(self, tmp_path, monkeypatch):
        """OPENCUT_DOMAIN_CACHE_TTL=0 -> 每次重载（开发热改）。"""
        monkeypatch.setenv("OPENCUT_DOMAINS_DIR", str(tmp_path))
        monkeypatch.setenv("OPENCUT_DOMAIN_CACHE_TTL", "0")
        (tmp_path / "education").mkdir()
        (tmp_path / "education" / "style.yaml").write_text("visual:\n  active_color: red", encoding="utf-8")
        c1 = config.get_domain_config("education")
        c2 = config.get_domain_config("education")
        assert c1 is not c2  # TTL=0 -> 新实例

    def test_clear_cache(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENCUT_DOMAINS_DIR", str(tmp_path))
        (tmp_path / "education").mkdir()
        (tmp_path / "education" / "style.yaml").write_text("visual:\n  active_color: red", encoding="utf-8")
        c1 = config.get_domain_config("education")
        config.clear_domain_cache()
        c2 = config.get_domain_config("education")
        assert c1 is not c2  # 清缓存后新实例

    def test_invalid_ttl_falls_back_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENCUT_DOMAINS_DIR", str(tmp_path))
        monkeypatch.setenv("OPENCUT_DOMAIN_CACHE_TTL", "not-a-number")
        (tmp_path / "education").mkdir()
        (tmp_path / "education" / "style.yaml").write_text("visual:\n  active_color: red", encoding="utf-8")
        c1 = config.get_domain_config("education")
        c2 = config.get_domain_config("education")
        # 无效 TTL -> 默认 60s -> 缓存命中
        assert c1 is c2
