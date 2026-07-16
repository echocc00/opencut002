"""画面匹配 Agent - AI 匹配打分 + 缺口分层决策

每段按匹配度 s 分层：
- s ≥ STRONG(0.7)：直接用匹配池图
- WEAK(0.4) ≤ s < STRONG：第1层，用弱匹配池图（AI 已判相关，复用）
- s < WEAK：缺口 -> 第3层生图（opt-in，缺口多时）或 第2层文字卡

阈值 + 生图开关走环境变量，可调。每段决策写 layer_log + log.info 便于观测调参。
"""
from __future__ import annotations
import logging
import os
from typing import Any

from ..orchestrator.state import ProjectState, StageState
from ..providers.selector import TaskType
from ..tools.image_matcher import match_images
from .base_agent import BaseStageAgent

log = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


STRONG = _env_float("OPENCUT_MATCH_STRONG", 0.7)
WEAK = _env_float("OPENCUT_MATCH_WEAK", 0.4)
GEN_TRIGGER_COUNT = _env_int("OPENCUT_GEN_TRIGGER_COUNT", 3)
GEN_TRIGGER_RATIO = _env_float("OPENCUT_GEN_TRIGGER_RATIO", 0.4)


def _gen_enabled() -> bool:
    return os.environ.get("OPENCUT_IMAGE_GEN", "").strip().lower() in ("1", "true", "yes", "on")


class ImageMatchingAgent(BaseStageAgent):
    def get_task_type(self) -> TaskType:
        return TaskType.GENERAL

    async def execute(self, state: ProjectState, stage: StageState) -> dict[str, Any]:
        cw_output = state.get_stage_output("copywriting")
        ma_output = state.get_stage_output("material_analysis")
        if not cw_output or not ma_output:
            return {"data": {"matches": {}, "text_cards": []}, "confidence": 30.0}

        paragraphs = cw_output.get("paragraphs", [])
        images = ma_output.get("images", [])

        # AI 匹配 + 打分（候选过滤到已注册 provider，避免 selector 选到未注册的）
        ai_complete = None
        try:
            from ..providers.provider_registry import get_provider, list_providers
            from ..providers.selector import ProviderSelector
            registered = list_providers()
            candidates = [p for p in ["minimax", "deepseek", "doubao", "qwen"] if p in registered]
            if candidates:
                selector = ProviderSelector()
                sel = selector.select(TaskType.GENERAL, candidates)
                ai_complete = get_provider(sel.winner).complete
        except Exception:
            pass

        raw = await match_images(paragraphs, images, ai_complete)

        # 缺口统计（s < WEAK）
        gap_indices = [i for i in range(len(paragraphs))
                       if raw.get(str(i), {}).get("score", 0.0) < WEAK]
        gap_ratio = len(gap_indices) / max(len(paragraphs), 1)
        do_gen = _gen_enabled() and (len(gap_indices) >= GEN_TRIGGER_COUNT
                                     or gap_ratio >= GEN_TRIGGER_RATIO)

        final_matches: dict[str, str] = {}
        text_cards: list[int] = []
        layer_log: list[str] = []

        for i in range(len(paragraphs)):
            entry = raw.get(str(i), {"image": "", "score": 0.0})
            score = float(entry.get("score", 0.0))
            img = entry.get("image", "")

            if score >= STRONG:
                final_matches[str(i)] = img
                layer_log.append(f"段落{i}: s={score:.2f} 直接匹配")
            elif score >= WEAK:
                final_matches[str(i)] = img  # 第1层：弱匹配复用
                layer_log.append(f"段落{i}: s={score:.2f} 第1层弱匹配复用")
            else:  # 缺口
                if do_gen:
                    try:
                        from ..tools.image_generator import generate_image
                        from ..providers.fallback import call_tool_with_fallback
                        # v0.6.2: per-tool fallback 机制就位（fallback_fns 待加本地 SD 等替代）
                        gen_path = await call_tool_with_fallback(
                            generate_image, fallback_fns=[],
                            paragraph_text=paragraphs[i].get("text", ""),
                            ma_output=ma_output, project_id=state.project_id, index=i)
                        final_matches[str(i)] = gen_path
                        layer_log.append(f"段落{i}: s={score:.2f} 第3层生图")
                    except Exception as e:
                        log.warning("段落%s 生图失败，回退文字卡: %s", i, e)
                        text_cards.append(i)
                        final_matches[str(i)] = ""
                        layer_log.append(f"段落{i}: s={score:.2f} 第2层文字卡(生图失败)")
                else:
                    text_cards.append(i)
                    final_matches[str(i)] = ""
                    layer_log.append(f"段落{i}: s={score:.2f} 第2层文字卡")

        for line in layer_log:
            log.info(line)

        return {"data": {"matches": final_matches, "text_cards": text_cards,
                         "layer_log": layer_log},
                "confidence": 75.0}

    def _build_prompt(self, *a): return ""
    def _parse_output(self, r): return {}
