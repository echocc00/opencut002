"""M17-M21 验收测试: 高级功能"""
import tempfile
from pathlib import Path

import pytest

# M17: 审批模式 + 偏好画像
from src.orchestrator.approval_controller import should_pause_for_review, get_auto_retry_limit
from src.orchestrator.preference_profile import PreferenceProfile

# M18: 置信度评分
from src.agents.confidence_scorer import calculate_confidence, get_required_keys

# M19: 参考视频 (导入检查)
from src.tools.video_downloader import download_video
from src.tools.scene_detector import detect_scenes, extract_keyframes
from src.agents.reference_analyzer_agent import ReferenceAnalyzerAgent

# M20: 监控面板
from src.api.panel_routes import router as panel_router

# M21: 标注回流
from src.observability.annotation_store import AnnotationStore, POSITIVE_TAGS, NEGATIVE_TAGS


class TestM17ApprovalController:
    def test_manual_mode_decision_pauses(self):
        assert should_pause_for_review("decision", "manual") is True

    def test_manual_mode_auto_skips(self):
        assert should_pause_for_review("auto", "manual") is False

    def test_full_auto_never_pauses(self):
        assert should_pause_for_review("decision", "full_auto") is False
        assert should_pause_for_review("quality_gate", "full_auto") is False

    def test_semi_auto_high_confidence_skips(self):
        assert should_pause_for_review("decision", "semi_auto", 85) is False

    def test_semi_auto_low_confidence_pauses(self):
        assert should_pause_for_review("decision", "semi_auto", 50) is True

    def test_retry_limits(self):
        assert get_auto_retry_limit("full_auto") == 3
        assert get_auto_retry_limit("semi_auto") == 1
        assert get_auto_retry_limit("manual") == 0


class TestM17PreferenceProfile:
    def test_load_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = PreferenceProfile(Path(tmp), "test_user")
            assert p.get_preference("domain") == "travel"
            assert p.get_preference("preferred_voice") == ""

    def test_record_and_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = PreferenceProfile(Path(tmp), "test_user")
            p.record_decision("voice_selection", "magnetic_male", confidence=85)
            assert p.get_preference("preferred_voice") == "magnetic_male"
            assert p.data["total_videos_produced"] == 1

            # 重新加载
            p2 = PreferenceProfile(Path(tmp), "test_user")
            assert p2.get_preference("preferred_voice") == "magnetic_male"

    def test_record_topic_updates_hook_style(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = PreferenceProfile(Path(tmp), "test_user")
            p.record_decision("topic", {"directions": [{"hook": "suspense"}], "selected": 0})
            assert p.get_preference("preferred_hook_style") == "suspense"


class TestM18ConfidenceScorer:
    def test_empty_output_low(self):
        assert calculate_confidence({}) == 20.0

    def test_full_output_high(self):
        output = {"a": "val", "b": [1, 2], "c": "val"}
        assert calculate_confidence(output) >= 50.0

    def test_missing_required_keys_lowers_score(self):
        output = {"a": "val"}
        assert calculate_confidence(output, required_keys=["a", "b", "c"]) < 80.0

    def test_all_required_keys_present(self):
        output = {"a": "val", "b": "val", "c": "val"}
        assert calculate_confidence(output, required_keys=["a", "b", "c"]) >= 50.0

    def test_empty_lists_lower_score(self):
        output = {"a": [], "b": "val", "c": "val"}
        score = calculate_confidence(output)
        assert score < 90.0

    def test_stage_required_keys(self):
        assert "directions" in get_required_keys("topic")
        assert "paragraphs" in get_required_keys("copywriting")
        assert get_required_keys("nonexistent") is None


class TestM19ReferenceVideo:
    def test_reference_analyzer_importable(self):
        assert ReferenceAnalyzerAgent is not None

    def test_scene_detector_importable(self):
        assert detect_scenes is not None
        assert extract_keyframes is not None

    def test_video_downloader_importable(self):
        assert download_video is not None


class TestM20PanelRoutes:
    def test_router_has_routes(self):
        routes = [r.path for r in panel_router.routes]
        assert any("status" in r for r in routes)
        assert any("decisions" in r for r in routes)
        assert any("quality" in r for r in routes)


class TestM21AnnotationStore:
    def test_add_and_retrieve(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AnnotationStore(Path(tmp))
            store.add_annotation("vid1", "proj1",
                positive_tags=["opening_grabbing", "bgm_matching"],
                negative_tags=[], overall_rating=5)
            store.add_annotation("vid2", "proj2",
                positive_tags=["opening_grabbing"],
                negative_tags=["pacing_drag"], overall_rating=3)

            top = store.get_top_rated(min_rating=4)
            assert len(top) == 1
            assert top[0]["video_id"] == "vid1"

    def test_positive_tags_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AnnotationStore(Path(tmp))
            store.add_annotation("v1", "p1", ["opening_grabbing", "bgm_matching"], [], 5)
            store.add_annotation("v2", "p2", ["opening_grabbing", "copywriting_engaging"], [], 4)
            tags = store.get_positive_tags_summary(min_rating=4)
            assert tags["opening_grabbing"] == 2
            assert tags["bgm_matching"] == 1

    def test_build_guidance_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AnnotationStore(Path(tmp))
            store.add_annotation("v1", "p1", ["opening_grabbing", "bgm_matching"], [], 5)
            prompt = store.build_guidance_prompt(min_rating=4)
            assert "开头抓人" in prompt
            assert "BGM踩点准" in prompt

    def test_empty_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AnnotationStore(Path(tmp))
            assert store.build_guidance_prompt() == ""

    def test_tag_constants(self):
        assert len(POSITIVE_TAGS) == 6
        assert len(NEGATIVE_TAGS) == 6
