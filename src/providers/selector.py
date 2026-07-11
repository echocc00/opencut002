"""Provider 7维度评分选择引擎 - 从YAML加载配置"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml


class TaskType(str, Enum):
    TOPIC_GENERATION = "topic_generation"
    COPYWRITING = "copywriting"
    IMAGE_ANALYSIS = "image_analysis"
    STORYBOARD = "storyboard"
    BGM_SELECTION = "bgm_selection"
    RHYTHM = "rhythm"
    PUBLISHING = "publishing"
    COVER = "cover"
    FINE_CUT = "fine_cut"
    WEB_RESEARCH = "web_research"
    GENERAL = "general"


@dataclass
class ProviderScore:
    provider_name: str
    total_score: float = 0.0
    dimensions: dict[str, float] = field(default_factory=lambda: {
        "task_fit": 0.0, "output_quality": 0.0, "control": 0.0,
        "reliability": 0.0, "cost_efficiency": 0.0, "latency": 0.0,
        "continuity": 0.0,
    })


@dataclass
class SelectionResult:
    task_type: TaskType
    winner: str
    total_score: float
    scores: list[ProviderScore]
    timestamp: float = field(default_factory=time.time)
    reasoning: str = ""


class ProviderSelector:
    DEFAULT_CONFIG_PATH = "config/providers.yaml"

    def __init__(self, config_path: str | Path | None = None):
        """初始化时加载YAML配置，文件不存在则用内置默认值"""
        self.config_path = Path(config_path) if config_path else Path(self.DEFAULT_CONFIG_PATH)
        self._config = self._load_config()

    def _load_config(self) -> dict:
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        # 内置默认值（兼容旧代码）
        return {
            "weights": {"task_fit": 0.30, "output_quality": 0.20, "control": 0.15,
                        "reliability": 0.15, "cost_efficiency": 0.10, "latency": 0.05, "continuity": 0.05},
            "task_fit_matrix": {"topic_generation": {"doubao": 90, "deepseek": 85, "qwen": 80}},
            "output_quality": {"doubao": 78, "deepseek": 85, "qwen": 75},
            "control": {"doubao": 75, "deepseek": 82, "qwen": 72},
            "reliability": {"doubao": 85, "deepseek": 80, "qwen": 82},
            "cost_efficiency": {"doubao": 90, "deepseek": 92, "qwen": 88},
            "latency": {"doubao": 80, "deepseek": 78, "qwen": 82},
        }

    @property
    def WEIGHTS(self) -> dict[str, float]:
        return self._config.get("weights", {})

    def _get_matrix_value(self, matrix_name: str, provider: str,
                          task_type: TaskType | None = None) -> float:
        if matrix_name == "task_fit_matrix":
            if task_type:
                matrix = self._config.get("task_fit_matrix", {})
                task_key = task_type.value
                return matrix.get(task_key, {}).get(provider, 50)
            return 50
        return self._config.get(matrix_name, {}).get(provider, 60)

    def select(self, task_type: TaskType, candidates: list[str],
               previous_provider: Optional[str] = None,
               log_path: Optional[Path] = None) -> SelectionResult:
        scores: list[ProviderScore] = []
        for provider in candidates:
            ps = ProviderScore(provider_name=provider)
            ps.dimensions["task_fit"] = self._get_matrix_value("task_fit_matrix", provider, task_type)
            ps.dimensions["output_quality"] = self._get_matrix_value("output_quality", provider)
            ps.dimensions["control"] = self._get_matrix_value("control", provider)
            ps.dimensions["reliability"] = self._get_matrix_value("reliability", provider)
            ps.dimensions["cost_efficiency"] = self._get_matrix_value("cost_efficiency", provider)
            ps.dimensions["latency"] = self._get_matrix_value("latency", provider)
            ps.dimensions["continuity"] = 100 if (previous_provider and provider == previous_provider) else 50
            ps.total_score = sum(ps.dimensions[d] * w for d, w in self.WEIGHTS.items())
            scores.append(ps)

        scores.sort(key=lambda s: s.total_score, reverse=True)
        winner = scores[0].provider_name if scores else candidates[0]
        reasoning = self._reason(task_type, scores)

        result = SelectionResult(
            task_type=task_type, winner=winner,
            total_score=scores[0].total_score if scores else 0,
            scores=scores, reasoning=reasoning,
        )

        if log_path:
            self._log(result, log_path)
        return result

    def _reason(self, task_type: TaskType, scores: list[ProviderScore]) -> str:
        if not scores:
            return "no candidates"
        w = scores[0]
        strongest = max(w.dimensions, key=w.dimensions.get)
        labels = {"task_fit": "任务适配度", "output_quality": "输出质量", "control": "可控性",
                  "reliability": "可靠性", "cost_efficiency": "性价比", "latency": "响应速度",
                  "continuity": "一致性"}
        r = f"选择 {w.provider_name}（{w.total_score:.0f}分），优势在{labels.get(strongest, strongest)}（{w.dimensions[strongest]:.0f}）"
        if len(scores) > 1:
            ru = scores[1]
            r += f"。次选 {ru.provider_name}（{ru.total_score:.0f}），差距 {w.total_score - ru.total_score:.0f}"
        return r

    def _log(self, result: SelectionResult, log_path: Path):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": result.timestamp, "task_type": result.task_type.value,
                 "winner": result.winner, "score": result.total_score, "reasoning": result.reasoning,
                 "all_scores": [{"provider": s.provider_name, "total": s.total_score, "dims": s.dimensions}
                                for s in result.scores]}
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
