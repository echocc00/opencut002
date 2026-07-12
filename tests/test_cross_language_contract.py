"""跨语言数据契约测试 - 验证 Python 输出和 TypeScript 期望一致"""
import json
import re
from pathlib import Path


class TestFieldNameContract:
    """Python(snake_case) -> TypeScript(camelCase) 字段名匹配"""

    EXPECTED_TOP_LEVEL = {
        "title", "titleDuration", "segments", "voicePath",
        "bgmPath", "bgmVolume", "style", "coverImage",
    }

    EXPECTED_SEGMENT_FIELDS = {
        "index", "image", "actualDuration", "timeStart",
        "subtitle", "transition", "subtitleWords",
    }

    EXPECTED_WORD_FIELDS = {"word", "start", "end"}

    def test_build_render_data_uses_camelcase(self):
        """build_render_data 输出的字段名必须是 camelCase"""
        from src.tools.remotion_renderer import RemotionRenderer
        data = RemotionRenderer.build_render_data(
            title="test", title_duration=2.0,
            segments=[{"actual_duration": 3.0, "time_start": 0.0,
                       "subtitle_words": [{"word": "你", "start": 0.0, "end": 0.3}]}],
            voice_path="/voice.wav",
        )
        # 顶层字段
        for key in data.keys():
            assert "_" not in key or key in ("bgmPath", "bgmVolume"), \
                f"顶层字段 {key} 包含下划线（应为camelCase）"

        # segment 字段
        seg = data["segments"][0]
        assert "actualDuration" in seg, "缺少 actualDuration"
        assert "timeStart" in seg, "缺少 timeStart"
        assert "subtitleWords" in seg, "缺少 subtitleWords"
        assert "actual_duration" not in seg, "残留 actual_duration (snake_case)"
        assert "time_start" not in seg, "残留 time_start (snake_case)"
        assert "subtitle_words" not in seg, "残留 subtitle_words (snake_case)"

    def test_video_composition_expects_camelcase(self):
        """VideoComposition.tsx 读取的字段名必须是 camelCase"""
        content = Path("remotion/src/VideoComposition.tsx").read_text(encoding="utf-8")
        # 检查不包含 snake_case 访问
        snake_case_patterns = [
            "data.title_duration", "data.voice_path", "data.bgm_path",
            "data.bgm_volume", "seg.actual_duration", "seg.time_start",
            "seg.subtitle_words",
        ]
        for pattern in snake_case_patterns:
            assert pattern not in content, \
                f"VideoComposition.tsx 包含 snake_case 访问: {pattern}"

    def test_word_subtitle_renders_text(self):
        """WordByWordSubtitle 组件接收 text 整段显示（不逐词高亮）"""
        content = Path("remotion/src/components/WordByWordSubtitle.tsx").read_text(encoding="utf-8")
        assert "text" in content, "应有 text prop"
        # 不再逐词：不应有 w.start / w.word 访问
        assert "w.start" not in content and "w.word" not in content, "不应逐词访问"


class TestPathFormat:
    """路径格式标准测试"""

    def test_build_render_data_outputs_relative_paths(self):
        """build_render_data 输出的路径不应是绝对路径"""
        from src.tools.remotion_renderer import RemotionRenderer
        data = RemotionRenderer.build_render_data(
            title="test", title_duration=2.0,
            segments=[], voice_path="data/voice.wav",
            bgm_path="domains/travel/bgm/test.mp3",
        )
        # voicePath 和 bgmPath 应该保持传入的格式
        assert not data["voicePath"].startswith("/"), "voicePath 不应是绝对路径"
        assert not data["bgmPath"].startswith("/"), "bgmPath 不应是绝对路径"


class TestRemotionConstraints:
    """Remotion API 约束测试"""

    def test_subtitle_uses_spring_fadein(self):
        """字幕用 spring 做整段淡入（opacity），不逐词 interpolate 颜色"""
        content = Path("remotion/src/components/WordByWordSubtitle.tsx").read_text(encoding="utf-8")
        assert "spring" in content, "应用 spring 动画"
        assert "opacity" in content, "应淡入（opacity）"


class TestEnvironmentConstraints:
    """环境约束文档测试"""

    def test_data_flow_contract_has_remotion_section(self):
        """数据流契约文档应包含 Remotion 边界定义"""
        content = Path("docs/data-flow-contract.md").read_text(encoding="utf-8")
        assert "Remotion" in content or "remotion" in content, \
            "数据流契约应包含 Remotion 边界定义"
        assert "camelCase" in content, "应定义 camelCase 转换规则"
        assert "file://" in content or "base64" in content, \
            "应记录 Chrome file:// 约束"
