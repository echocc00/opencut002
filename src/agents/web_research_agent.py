"""Web 调研 Agent - 选题前搜索热门话题，产出结构化调研简报"""
from __future__ import annotations

import json
from typing import Any

from ..orchestrator.state import ProjectState, StageState
from ..providers.selector import TaskType
from ..tools.web_searcher import batch_search
from .base_agent import BaseStageAgent


class WebResearchAgent(BaseStageAgent):
    def get_task_type(self) -> TaskType:
        return TaskType.WEB_RESEARCH

    def _build_prompt(self, skill_context, upstream_context, user_note, input_data) -> str:
        materials = input_data.get("materials", [])
        destination = input_data.get("destination", "旅行")
        search_results = input_data.get("search_results", [])

        results_text = "\n\n".join(
            f"[{r.get('query', '')}] {r.get('text', '')}"
            for r in search_results[:15]
        ) or "无搜索结果"

        return f"""{skill_context}

【素材概况】
目的地/场景: {destination}
素材数量: {len(materials)}

【搜索结果】
{results_text}

{f'【用户备注】{user_note}' if user_note else ''}

请基于以上信息，产出一份调研简报。输出JSON：
{{
  "hot_topics": ["热门话题1", "热门话题2", "热门话题3"],
  "angle_suggestions": ["角度建议1", "角度建议2"],
  "avoid_angles": ["避坑角度1"],
  "differentiation": "差异化机会描述"
}}"""

    async def execute(self, state: ProjectState, stage: StageState) -> dict[str, Any]:
        """重写 execute：先搜索再调AI"""
        # 1. 从素材分析中提取目的地
        ma_output = state.get_stage_output("material_analysis")
        destination = ma_output.get("destination", "") if ma_output else ""
        if not destination and ma_output:
            scenes = [s.get("scene", "") for s in ma_output.get("images", []) if s.get("scene")]
            destination = scenes[0] if scenes else "旅行"

        # 2. 从领域配置加载搜索关键词模板
        research_config = self.skill_loader.domain.research
        queries = [
            q.replace("{destination}", destination)
            for q in research_config.get("search_queries", [f"{destination} 旅游攻略"])
        ]

        # 3. 执行搜索
        search_results = await batch_search(queries)

        # 4. 注入搜索结果到 input_data
        stage.input_data = {
            "destination": destination,
            "materials": ma_output.get("images", []) if ma_output else [],
            "search_results": search_results,
        }

        # 5. 调用父类 execute（走标准AI流程）
        result = await super().execute(state, stage)

        # 6. 合并搜索结果到输出
        result["data"]["raw_results"] = search_results
        return result

    def _parse_output(self, response: str) -> dict[str, Any]:
        parsed = self._extract_json(response)
        if not parsed:
            return {
                "hot_topics": [], "angle_suggestions": [],
                "avoid_angles": [], "differentiation": "",
            }
        return parsed
