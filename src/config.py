"""OpenCut v3.0 全局配置 + 领域配置加载"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPENCUT_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    domains_dir: Path = Path("domains")
    pipelines_dir: Path = Path("pipelines")
    remotion_dir: Path = Path("remotion")
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    remotion_fps: int = 30
    default_llm_provider: str = "deepseek"
    tts_speed: float = 1.0  # 配 minimax TTS 语速（仅 minimax 引擎生效）


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


class DomainConfig:
    """加载领域配置目录下的所有配置文件"""

    def __init__(self, domain_dir: Path):
        self.dir = Path(domain_dir)
        self.name = self.dir.name
        self.style: dict = self._load_yaml("style.yaml")
        self.highlights: dict = self._load_json("highlights.json")
        self.voices: dict = self._load_json("voices.json")
        self.research: dict = self._load_json("research.json")
        self.opening_templates: dict = self._load_yaml("opening_templates.yaml")

    def _load_yaml(self, filename: str) -> dict:
        path = self.dir / filename
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def _load_json(self, filename: str) -> dict:
        path = self.dir / filename
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def get_skill(self, stage_name: str) -> str:
        path = self.dir / "skills" / f"{stage_name}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def get_highlights(self) -> list[dict]:
        return self.highlights.get("highlights", [])

    def get_voices(self) -> dict[str, dict]:
        return self.voices

    def get_style(self) -> dict:
        return self.style


_domain_cache: dict[str, tuple[DomainConfig, float]] = {}


def get_domain_config(domain_name: str, domains_dir: Path | None = None) -> DomainConfig:
    """获取领域配置（v0.6.1 TTL 缓存）。

    OPENCUT_DOMAIN_CACHE_TTL 秒内复用缓存（默认 60s）；设 0 永远重载（开发热改 style.yaml）。
    """
    try:
        ttl = float(os.environ.get("OPENCUT_DOMAIN_CACHE_TTL", "60"))
    except (TypeError, ValueError):
        ttl = 60.0
    now = time.time()
    if domain_name in _domain_cache:
        config, load_time = _domain_cache[domain_name]
        # ttl>0 且在 TTL 内才命中；ttl<=0 永远重载（开发热改 style.yaml）
        if ttl > 0 and (now - load_time) < ttl:
            return config
    base = domains_dir or get_settings().domains_dir
    config = DomainConfig(Path(base) / domain_name)
    _domain_cache[domain_name] = (config, now)
    return config


def clear_domain_cache() -> None:
    """清领域配置缓存（测试用）。"""
    _domain_cache.clear()
