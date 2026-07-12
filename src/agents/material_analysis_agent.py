"""素材分析 Agent - 用多模态模型真实分析图片的场景、情绪、质量

关键：material_analysis 必须用视觉模型真正"看"图，不能只传文件名给文本模型
（否则 AI 会幻觉出与画面无关的内容，导致下游文案与素材完全对不上）。
"""
from __future__ import annotations
import logging
from typing import Any
from ..providers.selector import TaskType
from ..orchestrator.state import ProjectState, StageState
from .base_agent import BaseStageAgent

log = logging.getLogger(__name__)


class MaterialAnalysisAgent(BaseStageAgent):
    def get_task_type(self) -> TaskType:
        return TaskType.IMAGE_ANALYSIS

    async def execute(self, state: ProjectState, stage: StageState) -> dict[str, Any]:
        """重写 execute：用多模态 provider 真实分析图片内容"""
        import os
        from ..providers.provider_registry import list_providers, get_provider
        from ..providers.pricing import calc_cost

        materials = stage.input_data.get("materials", [])
        # 基础检查（文件大小->粗分），作为视觉分析失败时的兜底
        basic_analyses = []
        for m in materials:
            fpath = m.get("file", "")
            if fpath and os.path.exists(fpath):
                size = os.path.getsize(fpath)
                score = min(5, max(1, size // 100000))
                basic_analyses.append({"file": fpath, "size": size, "basic_score": score})
        stage.input_data["basic_analyses"] = basic_analyses

        # 选多模态 provider（优先 minimax M3，次选 doubao，都能看图）
        candidates = list_providers()
        if not candidates:
            raise RuntimeError("无可用 Provider，请配置环境变量")
        provider_name = "minimax" if "minimax" in candidates else (
            "doubao" if "doubao" in candidates else candidates[0])
        provider = get_provider(provider_name)

        image_paths = [m["file"] for m in materials if m.get("file") and os.path.exists(m["file"])]
        file_list = [m.get("filename", m.get("file", "")) for m in materials]
        prompt = f"""分析下方提供的 {len(image_paths)} 张图片（文件名依次为：{file_list}）。
根据图片【真实画面内容】分析每张图的场景、情绪、质量评分（1-5）。
推断这些图片共同的拍摄目的地/主题（destination）和场景类型（scene_types）。
输出JSON：
{{"images": [{{"file": "", "scene": "", "emotion": "", "score": 3}}], "destination": "", "scene_types": []}}
注意：images 数组按图片顺序填写，file 字段填对应文件名；scene/emotion 必须基于真实画面。"""

        response = None
        try:
            response = await provider.complete(prompt, images=image_paths)
            output = self._extract_json(response.text)
        except Exception as e:
            log.warning(f"视觉分析失败，回退到基础分析: {e}")
            output = {}

        # 确保 file 字段是完整路径（AI 可能只返回文件名），并补全缺失项
        images_out = output.get("images", [])
        for i, b in enumerate(basic_analyses):
            if i < len(images_out):
                images_out[i]["file"] = b["file"]  # 强制完整路径
                if not images_out[i].get("score"):
                    images_out[i]["score"] = b["basic_score"]
            else:
                images_out.append({"file": b["file"], "scene": "unknown",
                                   "emotion": "unknown", "score": b["basic_score"]})
        output["images"] = images_out
        output.setdefault("destination", "unknown")
        output.setdefault("scene_types", [])

        # 是否真实分析成功（至少一张 scene 非 unknown）
        real_analyzed = any(img.get("scene", "unknown") != "unknown" for img in images_out)
        confidence = 75.0 if real_analyzed else 45.0

        in_tok = response.input_tokens if response else 0
        out_tok = response.output_tokens if response else 0
        mdl = response.model if response else provider_name
        cost = calc_cost(in_tok, out_tok, provider_name)
        state.cost_total = state.cost_total + cost

        self.decision_logger.log(
            stage="material_analysis", provider=provider_name, provider_score=100,
            reasoning=f"多模态视觉分析 {len(image_paths)} 张图（{'成功' if real_analyzed else '回退基础'}）",
            confidence=confidence, output_summary=str(output)[:500],
            input_tokens=in_tok, output_tokens=out_tok, model=mdl,
            prompt_skill_file=f"domains/{state.domain}/skills/material_analysis.md",
            cost=cost,
        )

        return {
            "data": output,
            "confidence": confidence,
            "state_updates": {"last_provider": provider_name, "cost_total": state.cost_total},
        }

    def _build_prompt(self, skill_context, upstream_context, user_note, input_data):
        # 不再使用--execute 已重写为多模态视觉调用
        return ""

    def _parse_output(self, r):
        return self._extract_json(r)
