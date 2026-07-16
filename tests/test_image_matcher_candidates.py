"""image_matcher dedup 测试（v0.6.1）- 锁定 basename 冲突修复。"""
from __future__ import annotations

import asyncio

import pytest

from src.tools.image_matcher import _build_lookup, _resolve_match, match_images


class TestBuildLookup:
    def test_unique_basenames(self):
        files = ["/a/frame1.jpg", "/a/frame2.jpg"]
        full, base = _build_lookup(files)
        assert full == {"/a/frame1.jpg": "/a/frame1.jpg", "/a/frame2.jpg": "/a/frame2.jpg"}
        assert base == {"frame1.jpg": ["/a/frame1.jpg"], "frame2.jpg": ["/a/frame2.jpg"]}

    def test_duplicate_basenames_preserved(self):
        """修：旧版 {basename: full} 同名跨目录覆盖，新版保全部。"""
        files = ["/dir1/frame.jpg", "/dir2/frame.jpg"]
        full, base = _build_lookup(files)
        assert len(base["frame.jpg"]) == 2
        assert "/dir1/frame.jpg" in base["frame.jpg"]
        assert "/dir2/frame.jpg" in base["frame.jpg"]


class TestResolveMatch:
    def test_exact_full_path(self):
        full, base = _build_lookup(["/a/x.jpg"])
        assert _resolve_match("/a/x.jpg", full, base) == "/a/x.jpg"

    def test_basename_only(self):
        full, base = _build_lookup(["/a/x.jpg"])
        assert _resolve_match("x.jpg", full, base) == "/a/x.jpg"

    def test_duplicate_basename_returns_first(self):
        full, base = _build_lookup(["/dir1/frame.jpg", "/dir2/frame.jpg"])
        # 多候选取首个 + log 警告
        assert _resolve_match("frame.jpg", full, base) == "/dir1/frame.jpg"

    def test_no_match_returns_empty(self):
        full, base = _build_lookup(["/a/x.jpg"])
        assert _resolve_match("nope.jpg", full, base) == ""

    def test_empty_input(self):
        full, base = _build_lookup(["/a/x.jpg"])
        assert _resolve_match("", full, base) == ""


class TestMatchImagesDedup:
    @pytest.mark.asyncio
    async def test_same_basename_different_dirs_both_matchable(self):
        """修：旧版两个 frame.jpg 互相覆盖 -> 只能匹配一个；新版都能匹配。"""
        paragraphs = [{"text": "p0", "image_hint": ""}, {"text": "p1", "image_hint": ""}]
        images = [
            {"file": "/dir1/frame.jpg", "scene": "a"},
            {"file": "/dir2/frame.jpg", "scene": "b"},
        ]

        async def ai_complete(prompt):
            from src.providers.provider_registry import ProviderResponse
            # AI 返回两段都匹配 frame.jpg
            return ProviderResponse(text='{"matches": [{"paragraph": 0, "image": "/dir1/frame.jpg", "relevance": 0.9}, {"paragraph": 1, "image": "/dir2/frame.jpg", "relevance": 0.8}]}')

        result = await match_images(paragraphs, images, ai_complete)
        # 两段都能匹配到各自的完整路径（旧版会都映射到同一个）
        assert result["0"]["image"] == "/dir1/frame.jpg"
        assert result["1"]["image"] == "/dir2/frame.jpg"
        assert result["0"]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_no_ai_uses_hint(self):
        paragraphs = [{"text": "p0", "image_hint": "hint.jpg"}]
        images = [{"file": "/pool/hint.jpg", "scene": "x"}]
        result = await match_images(paragraphs, images, ai_complete=None)
        assert result["0"]["image"] == "/pool/hint.jpg"
        assert result["0"]["score"] == 1.0

    @pytest.mark.asyncio
    async def test_gap_paragraph_empty(self):
        paragraphs = [{"text": "p0"}, {"text": "p1"}]
        images = [{"file": "/a/x.jpg"}]

        async def ai_complete(prompt):
            from src.providers.provider_registry import ProviderResponse
            return ProviderResponse(text='{"matches": [{"paragraph": 0, "image": "x.jpg", "relevance": 0.9}]}')

        result = await match_images(paragraphs, images, ai_complete)
        assert result["0"]["image"] == "/a/x.jpg"
        # p1 无匹配 -> 缺口
        assert result["1"]["image"] == ""
        assert result["1"]["score"] == 0.0
