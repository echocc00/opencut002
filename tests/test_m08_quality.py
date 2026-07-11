"""M08 验收测试: 质量治理系统"""
from src.quality.preflight import check_prerequisites
from src.quality.postflight import validate_output, check_output_completeness
from src.quality.slideshow_scorer import score_storyboard, RiskScore
from src.orchestrator.state import ProjectState, StageStatus


# ========== 前置校验 ==========

def test_preflight_passes_when_prerequisites_met():
    state = ProjectState(project_id="test")
    state.mark_stage("material_analysis", StageStatus.COMPLETED)
    state.mark_stage("web_research", StageStatus.COMPLETED)
    ok, issues = check_prerequisites(state, ["material_analysis", "web_research"])
    assert ok
    assert len(issues) == 0


def test_preflight_fails_when_prerequisite_missing():
    state = ProjectState(project_id="test")
    state.mark_stage("material_analysis", StageStatus.COMPLETED)
    ok, issues = check_prerequisites(state, ["material_analysis", "web_research"])
    assert not ok
    assert "前置阶段 web_research 未完成" in issues


# ========== 后置校验 ==========

def test_postflight_validates_topic_output():
    output = {"directions": [{"name": "测试", "hook": "suspense"}], "selected": 0}
    ok, issues = validate_output("topic", output)
    assert ok


def test_postflight_catches_invalid_output():
    output = {"directions": "not_a_list"}  # 类型错误
    ok, issues = validate_output("topic", output)
    assert not ok
    assert len(issues) > 0


def test_postflight_completeness_check_copywriting():
    """文案完整性检查 - 每段必须有 highlight_ref"""
    output = {
        "paragraphs": [
            {"text": "你好", "highlight_ref": "mystery_hook"},
            {"text": "世界", "highlight_ref": ""},  # 缺少 highlight_ref
        ],
        "tone": "emotional",
    }
    ok, issues = check_output_completeness("copywriting", output)
    assert not ok
    assert any("highlight_ref" in i for i in issues)


def test_postflight_completeness_empty_storyboard():
    ok, issues = check_output_completeness("storyboard", {"segments": []})
    assert not ok
    assert "分镜段落数据为空" in issues


# ========== 幻灯片风险评分 ==========

def test_slideshow_low_risk():
    """多样化分镜 -> 低风险"""
    segments = [
        {"image": "img1.jpg", "actual_duration": 3.0, "ab_split": True, "subtitle": "短字幕"},
        {"image": "img2.jpg", "actual_duration": 4.0, "ab_split": False, "subtitle": "另一段"},
        {"image": "img3.jpg", "actual_duration": 3.5, "ab_split": True, "subtitle": "第三段"},
        {"image": "img4.jpg", "actual_duration": 3.0, "ab_split": False, "subtitle": "第四段"},
    ]
    score = score_storyboard(segments)
    assert score.total_score < 70
    assert score.passed


def test_slideshow_critical_no_segments():
    """无分镜数据 -> critical"""
    score = score_storyboard([])
    assert score.risk_level == "critical"
    assert not score.passed


def test_slideshow_high_repetition():
    """高重复度 -> 高风险"""
    segments = [
        {"image": "same.jpg", "actual_duration": 5.0, "ab_split": False, "subtitle": "字幕"},
        {"image": "same.jpg", "actual_duration": 5.0, "ab_split": False, "subtitle": "字幕"},
        {"image": "same.jpg", "actual_duration": 5.0, "ab_split": False, "subtitle": "字幕"},
        {"image": "same.jpg", "actual_duration": 5.0, "ab_split": False, "subtitle": "字幕"},
    ]
    score = score_storyboard(segments)
    assert score.dimensions["repetition"] > 50
    assert any("重复" in s for s in score.suggestions)


def test_slideshow_weak_motion():
    """弱动态 -> 高分"""
    segments = [
        {"image": "img1.jpg", "actual_duration": 6.0, "ab_split": False, "subtitle": "字幕"},
        {"image": "img2.jpg", "actual_duration": 6.0, "ab_split": False, "subtitle": "字幕"},
    ]
    score = score_storyboard(segments)
    assert score.dimensions["weak_motion"] > 50


def test_slideshow_six_dimensions_present():
    """6 个维度都有分数"""
    segments = [{"image": "img1.jpg", "actual_duration": 3.0, "subtitle": "字幕"}]
    score = score_storyboard(segments)
    assert len(score.dimensions) == 6
    for dim in ["repetition", "weak_motion", "decorative_visuals",
                "shot_intent", "typography_overreliance", "unsupported_cinematic"]:
        assert dim in score.dimensions


def test_slideshow_suggestions_generated():
    """改进建议根据评分生成"""
    segments = [
        {"image": "same.jpg", "actual_duration": 6.0, "ab_split": False, "subtitle": "字幕" * 30},
    ] * 4
    score = score_storyboard(segments)
    assert len(score.suggestions) > 0


# ========== 渲染后自检 ==========

def test_post_render_missing_file():
    """文件不存在 -> 未通过"""
    from src.quality.post_render_validator import validate_video
    result = validate_video("/nonexistent/video.mp4")
    assert not result.passed
    assert "视频文件不存在" in result.issues[0]


def test_post_render_report_format():
    """报告格式正确"""
    from src.quality.post_render_validator import format_report, ValidationResult
    result = ValidationResult(passed=True, duration=45.0, resolution="1080x1920",
                              has_audio=True, subtitle_present=True)
    report = format_report(result)
    assert "视频质量验证报告" in report
    assert "通过" in report
    assert "45.0s" in report
