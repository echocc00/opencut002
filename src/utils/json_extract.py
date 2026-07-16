"""共享 JSON 提取工具 - 从 LLM 文本中稳健地抽出第一个 JSON 对象。

修复 v0.5.4 audit 的 _extract_json 括号深度匹配 bug：旧版不感知字符串上下文，
遇到 JSON 字符串值里的 `{` / `}`（如代码片段）会误判深度，导致合法响应被丢弃。
本版跟踪 inside-string 状态 + 反斜杠转义，字符串内的括号不影响深度计数。
"""
from __future__ import annotations

import json
import re


def extract_json_object(text: str) -> dict:
    """从文本中提取第一个完整 JSON 对象（字符串感知括号深度匹配）。

    找不到或解析失败返回 {}（与历史行为一致，调用方按空输出处理）。
    """
    if not text:
        return {}
    start = text.find("{")
    if start < 0:
        return {}

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        # 不在字符串内
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start:i + 1]
                try:
                    parsed = json.loads(candidate)
                    return parsed if isinstance(parsed, dict) else {}
                except json.JSONDecodeError:
                    break  # 首个闭合失败，回退 regex

    # 回退：非贪婪 regex（覆盖括号匹配够不到的边界情况）
    m = re.search(r"\{[\s\S]*?\}", text)
    if m:
        try:
            parsed = json.loads(m.group())
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            pass
    return {}
