"""M10 验收测试: Remotion 渲染管道"""
import json
from pathlib import Path

from src.tools.remotion_renderer import RemotionRenderer


def test_build_render_data_basic():
    """构建渲染数据 - 基本字段完整"""
    data = RemotionRenderer.build_render_data(
        title="敦煌探秘",
        title_duration=2.0,
        segments=[
            {
                "image": "/abs/path/img1.jpg",
                "actual_duration": 3.5,
                "time_start": 0.0,
                "subtitle": "你见过凌晨四点的敦煌吗",
                "subtitleWords": [
                    {"word": "你", "start": 0.0, "end": 0.3},
                    {"word": "见过", "start": 0.3, "end": 0.6},
                ],
                "transition": "crossfade",
            }
        ],
        voice_path="/abs/path/voice.wav",
        bgm_path="/abs/path/bgm.mp3",
        bgm_volume=0.25,
    )
    assert data["title"] == "敦煌探秘"
    assert data["titleDuration"] == 2.0
    assert len(data["segments"]) == 1
    assert data["segments"][0]["subtitleWords"][0]["word"] == "你"
    assert data["voicePath"] == "/abs/path/voice.wav"
    assert data["bgmPath"] == "/abs/path/bgm.mp3"
    assert data["bgmVolume"] == 0.25


def test_build_render_data_default_style():
    """默认样式配置正确"""
    data = RemotionRenderer.build_render_data(
        title="测试", title_duration=1.0, segments=[],
        voice_path="/voice.wav",
    )
    assert data["style"]["activeColor"] == "#D4734A"
    assert data["style"]["pastColor"] == "#A9A49C"
    assert data["style"]["upcomingColor"] == "#78736C"


def test_build_render_data_custom_style():
    """自定义样式覆盖默认值"""
    data = RemotionRenderer.build_render_data(
        title="测试", title_duration=1.0, segments=[],
        voice_path="/voice.wav",
        style={"activeColor": "#FF0000"},
    )
    assert data["style"]["activeColor"] == "#FF0000"
    # 其他样式保持默认
    assert data["style"]["pastColor"] == "#A9A49C"


def test_remotion_components_exist():
    """Remotion 组件文件全部存在"""
    base = Path(__file__).parent.parent / "remotion" / "src"
    expected_files = [
        "Root.tsx",
        "VideoComposition.tsx",
        "index.ts",
        "scenes/TitleScene.tsx",
        "scenes/SegmentScene.tsx",
        "components/WordByWordSubtitle.tsx",
    ]
    for f in expected_files:
        path = base / f
        assert path.exists(), f"Remotion 组件不存在: {f}"
        content = path.read_text(encoding="utf-8")
        assert len(content) > 50, f"组件内容过短: {f}"


def test_word_by_word_subtitle_component_structure():
    """字幕组件整段淡入结构（text prop + spring opacity）"""
    path = Path(__file__).parent.parent / "remotion" / "src" / "components" / "WordByWordSubtitle.tsx"
    content = path.read_text(encoding="utf-8")
    assert "text" in content  # text prop（整段文本）
    assert "spring" in content  # spring 入场动画
    assert "opacity" in content  # 淡入


def test_title_scene_has_spring_animation():
    """标题场景包含弹簧动画"""
    path = Path(__file__).parent.parent / "remotion" / "src" / "scenes" / "TitleScene.tsx"
    content = path.read_text(encoding="utf-8")
    assert "spring" in content  # 弹簧动画
    assert "scale" in content  # 缩放
    assert "interpolate" in content  # 透明度插值


def test_video_composition_has_audio():
    """视频组合组件包含音频轨道"""
    path = Path(__file__).parent.parent / "remotion" / "src" / "VideoComposition.tsx"
    content = path.read_text(encoding="utf-8")
    assert "Audio" in content or "Soundtrack" in content  # 音频组件
    assert "voicePath" in content  # 配音路径
    assert "bgmPath" in content  # BGM 路径
    assert "Sequence" in content  # 场景序列


def test_render_data_json_serializable():
    """渲染数据可序列化为 JSON"""
    data = RemotionRenderer.build_render_data(
        title="测试", title_duration=2.0,
        segments=[{"image": "img.jpg", "actual_duration": 3.0, "time_start": 0.0,
                   "subtitle": "字幕", "subtitleWords": [], "transition": "crossfade"}],
        voice_path="/voice.wav",
    )
    json_str = json.dumps(data, ensure_ascii=False)
    parsed = json.loads(json_str)
    assert parsed["title"] == "测试"


def test_package_json_exists():
    """Remotion package.json 存在且配置正确"""
    path = Path(__file__).parent.parent / "remotion" / "package.json"
    pkg = json.loads(path.read_text(encoding="utf-8"))
    assert pkg["name"] == "opencut-remotion"
    assert "remotion" in pkg["dependencies"]
    assert "@remotion/cli" in pkg["devDependencies"]
