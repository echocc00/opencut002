"""技能文件加载器 - 从 Markdown 提取结构化指导信息"""
from __future__ import annotations

import re

from src.config import DomainConfig


class SkillLoader:
    def __init__(self, domain_config: DomainConfig):
        self.domain = domain_config

    def load(self, stage_name: str) -> dict:
        content = self.domain.get_skill(stage_name)
        if not content:
            return {
                "content": "", "purpose": "", "quality_rules": [],
                "anti_patterns": [], "output_contract": [], "guidance": "",
            }
        return {
            "content": content,
            "purpose": self._extract_section_text(content, "## Purpose"),
            "quality_rules": self._extract_list(content, "## Quality Rules"),
            "anti_patterns": self._extract_list(content, "## Anti-Patterns"),
            "output_contract": self._extract_list(content, "## Output Contract"),
            "guidance": self._extract_section_text(content, "## Domain-Specific Guidance"),
        }

    def build_prompt_context(self, stage_name: str) -> str:
        skill = self.load(stage_name)
        parts: list[str] = []
        if skill["purpose"]:
            parts.append(f"【阶段目标】\n{skill['purpose']}")
        if skill["output_contract"]:
            parts.append("【输出要求】")
            parts.extend(f"- {r}" for r in skill["output_contract"])
        if skill["quality_rules"]:
            parts.append("【质量规则 - 必须遵守】")
            parts.extend(f"- {r}" for r in skill["quality_rules"])
        if skill["anti_patterns"]:
            parts.append("【禁止事项】")
            parts.extend(f"- {r}" for r in skill["anti_patterns"])
        if skill["guidance"]:
            parts.append(f"【领域指导】\n{skill['guidance']}")
        return "\n\n".join(parts)

    def _extract_list(self, content: str, header: str) -> list[str]:
        """提取 Markdown 列表项，支持 - 和 1. 两种格式"""
        lines = content.split("\n")
        capturing = False
        items: list[str] = []
        # 匹配 "- item" 或 "1. item" 或 "2. item"
        list_pattern = re.compile(r"^(?:-\s+|\d+\.\s+)(.+)")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(header):
                capturing = True
                continue
            if capturing and stripped.startswith("## "):
                break
            if capturing:
                match = list_pattern.match(stripped)
                if match:
                    items.append(match.group(1).strip())
        return items

    def _extract_section_text(self, content: str, header: str) -> str:
        lines = content.split("\n")
        capturing = False
        text_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(header):
                capturing = True
                continue
            if capturing and stripped.startswith("## "):
                break
            if capturing:
                text_lines.append(line)
        return "\n".join(text_lines).strip()
