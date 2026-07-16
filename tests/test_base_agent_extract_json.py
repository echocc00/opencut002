r"""JSON 提取测试（v0.6.1）- 锁定字符串感知括号深度（修旧贪婪 regex bug）。

旧版 `re.search(r"\{[\s\S]*\}")` 贪婪匹配首尾大括号，遇到：
- 嵌套 JSON：取最外层（碰巧对），但
- 字符串内大括号（如代码片段 `{ return a; }`）：误判深度，截断或丢弃合法响应
"""
from __future__ import annotations

from src.utils.json_extract import extract_json_object


class TestExtractJson:
    def test_empty(self):
        assert extract_json_object("") == {}
        assert extract_json_object("no json here") == {}

    def test_simple(self):
        assert extract_json_object('{"a": 1}') == {"a": 1}

    def test_with_surrounding_text(self):
        text = 'noise before {"a": 1} noise after'
        assert extract_json_object(text) == {"a": 1}

    def test_nested(self):
        assert extract_json_object('{"a": {"b": 1}}') == {"a": {"b": 1}}

    def test_braces_inside_string_not_counted(self):
        """修旧版 bug：字符串内 { } 不影响深度。"""
        text = '{"code": "if (x) { return y; }", "ok": true}'
        r = extract_json_object(text)
        assert r == {"code": "if (x) { return y; }", "ok": True}

    def test_escaped_quote_inside_string(self):
        text = r'{"msg": "she said \"hi\" {x}"}'
        r = extract_json_object(text)
        assert r == {"msg": 'she said "hi" {x}'}

    def test_non_dict_returns_empty(self):
        # 数组不是 dict -> 返回 {}
        assert extract_json_object("[1, 2, 3]") == {}

    def test_first_object_wins(self):
        text = '{"a": 1} {"b": 2}'
        r = extract_json_object(text)
        assert r == {"a": 1}

    def test_malformed_falls_back_to_regex(self):
        """括号匹配失败时回退非贪婪 regex。"""
        # 缺少闭合大括号但内部有合法子对象
        text = 'prefix {"a": 1} trailing'
        assert extract_json_object(text) == {"a": 1}
