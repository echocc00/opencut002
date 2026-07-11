"""工具模块覆盖率补充测试 - image_matcher / migration / post_render_validator / web_searcher"""
import json
from unittest.mock import patch, AsyncMock, MagicMock
import pytest


# ========== image_matcher ==========
class TestImageMatcher:
    def test_build_matching_prompt_contains_paragraphs_and_images(self):
        from src.tools.image_matcher import build_matching_prompt
        prompt = build_matching_prompt(
            [{"text": "你好", "image_hint": "img1.jpg"}],
            [{"scene": "风景", "file": "img1.jpg"}],
        )
        assert "你好" in prompt
        assert "img1.jpg" in prompt
        assert "matches" in prompt

    @pytest.mark.asyncio
    async def test_match_images_ai_path(self):
        from src.tools.image_matcher import match_images

        async def mock_ai(prompt):
            return '{"matches": [{"paragraph": 0, "image": "img1.jpg"}, {"paragraph": 1, "image": "img2.jpg"}]}'

        result = await match_images(
            [{"text": "a", "image_hint": ""}, {"text": "b", "image_hint": ""}],
            [{"file": "img1.jpg"}, {"file": "img2.jpg"}],
            ai_complete=mock_ai,
        )
        assert result["0"] == "img1.jpg"
        assert result["1"] == "img2.jpg"

    @pytest.mark.asyncio
    async def test_match_images_fallback_uses_hint(self):
        from src.tools.image_matcher import match_images
        result = await match_images(
            [{"text": "a", "image_hint": "hint.jpg"}],
            [{"file": "img1.jpg"}],
            ai_complete=None,
        )
        assert result["0"] == "hint.jpg"

    @pytest.mark.asyncio
    async def test_match_images_fallback_sequential(self):
        from src.tools.image_matcher import match_images
        result = await match_images(
            [{"text": "a"}, {"text": "b"}],
            [{"file": "first.jpg"}, {"file": "second.jpg"}],
            ai_complete=None,
        )
        assert result["0"] == "first.jpg"
        assert result["1"] == "second.jpg"

    @pytest.mark.asyncio
    async def test_match_images_fallback_empty_when_no_images(self):
        from src.tools.image_matcher import match_images
        result = await match_images([{"text": "a"}], [], ai_complete=None)
        assert result["0"] == ""

    @pytest.mark.asyncio
    async def test_match_images_ai_failure_falls_back(self):
        from src.tools.image_matcher import match_images

        async def mock_ai(prompt):
            raise RuntimeError("AI error")

        result = await match_images(
            [{"text": "a", "image_hint": "hint.jpg"}],
            [{"file": "img1.jpg"}],
            ai_complete=mock_ai,
        )
        assert result["0"] == "hint.jpg"


# ========== migration ==========
class TestMigration:
    def test_migrate_tts_voices_copies_json(self, tmp_path):
        from src.tools.migration import migrate_tts_voices
        src = tmp_path / "voices.json"
        src.write_text('{"v1": {"name": "x", "edge_tts_voice": "y"}}', encoding="utf-8")
        tgt = tmp_path / "out" / "voices.json"
        assert migrate_tts_voices(src, tgt) == 1
        assert json.loads(tgt.read_text(encoding="utf-8"))["v1"]["edge_tts_voice"] == "y"

    def test_migrate_tts_voices_missing_source(self, tmp_path):
        from src.tools.migration import migrate_tts_voices
        assert migrate_tts_voices(tmp_path / "nope.json", tmp_path / "out.json") == 0

    def test_migrate_highlights_wraps_list(self, tmp_path):
        from src.tools.migration import migrate_highlights
        src = tmp_path / "h.json"
        src.write_text(json.dumps([{"id": "x"}]), encoding="utf-8")
        tgt = tmp_path / "out" / "h.json"
        assert migrate_highlights(src, tgt) == 1
        assert "highlights" in json.loads(tgt.read_text(encoding="utf-8"))

    def test_migrate_highlights_keeps_existing(self, tmp_path):
        from src.tools.migration import migrate_highlights
        src = tmp_path / "h.json"
        src.write_text('{"highlights": [{"id": "a"}, {"id": "b"}]}', encoding="utf-8")
        assert migrate_highlights(src, tmp_path / "o.json") == 2

    def test_migrate_bgm_library_copies_mp3s(self, tmp_path):
        from src.tools.migration import migrate_bgm_library
        src = tmp_path / "bgm"
        src.mkdir()
        (src / "a.mp3").write_bytes(b"mp3")
        (src / "b.mp3").write_bytes(b"mp3")
        (src / "c.txt").write_text("no")
        tgt = tmp_path / "out" / "bgm"
        assert migrate_bgm_library(src, tgt) == 2
        assert (tgt / "a.mp3").exists()
        assert not (tgt / "c.txt").exists()

    def test_migrate_bgm_library_missing(self, tmp_path):
        from src.tools.migration import migrate_bgm_library
        assert migrate_bgm_library(tmp_path / "nope", tmp_path / "out") == 0

    def test_migrate_pipeline_renames_stages(self, tmp_path):
        from src.tools.migration import migrate_pipeline_v2_to_v3
        src = tmp_path / "v2.yaml"
        src.write_text(
            'pipeline:\n  name: v2\n  stages:\n'
            '    - {name: image_analysis, type: auto}\n'
            '    - {name: script, type: auto}\n',
            encoding="utf-8")
        tgt = tmp_path / "v3.yaml"
        assert migrate_pipeline_v2_to_v3(str(src), str(tgt)) == 2
        import yaml
        v3 = yaml.safe_load(tgt.read_text(encoding="utf-8"))
        names = [s["name"] for s in v3["pipeline"]["stages"]]
        assert "material_analysis" in names
        assert "copywriting" in names

    def test_migrate_pipeline_missing(self, tmp_path):
        from src.tools.migration import migrate_pipeline_v2_to_v3
        assert migrate_pipeline_v2_to_v3(str(tmp_path / "no.yaml"), str(tmp_path / "o.yaml")) == 0

    def test_migrate_state_v2_to_v3(self, tmp_path):
        from src.tools.migration import migrate_state_v2_to_v3
        src = tmp_path / "v2state.json"
        src.write_text(json.dumps({
            "project_id": "p1",
            "display_name": "x",
            "stages": {"image_analysis": {"status": "completed"}},
        }), encoding="utf-8")
        v3 = migrate_state_v2_to_v3(str(src), str(tmp_path / "v3state.json"))
        assert v3["name"] == "x"
        assert "material_analysis" in v3["stages"]
        assert v3["mode"] == "material"

    def test_migrate_state_missing(self, tmp_path):
        from src.tools.migration import migrate_state_v2_to_v3
        assert migrate_state_v2_to_v3(str(tmp_path / "no.json"), str(tmp_path / "o.json")) == {}

    def test_migrate_ffmpeg_audio_code_checks_existence(self, tmp_path):
        from src.tools.migration import migrate_ffmpeg_audio_code
        f = tmp_path / "x.py"
        f.write_text("code")
        assert migrate_ffmpeg_audio_code(f) is True
        assert migrate_ffmpeg_audio_code(tmp_path / "no.py") is False


# ========== post_render_validator ==========
class TestPostRenderValidator:
    def test_validate_video_missing_file(self, tmp_path):
        from src.quality.post_render_validator import validate_video
        result = validate_video(tmp_path / "nope.mp4")
        assert not result.passed
        assert "视频文件不存在" in result.issues[0]

    def test_validate_video_with_mocked_ffprobe(self, tmp_path):
        from src.quality.post_render_validator import validate_video
        video = tmp_path / "fake.mp4"
        video.write_bytes(b"fake")
        ffprobe_json = json.dumps({
            "streams": [
                {"codec_type": "video", "width": 1080, "height": 1920},
                {"codec_type": "audio"},
            ],
            "format": {"duration": "10.5"},
        })
        with patch("src.quality.post_render_validator.subprocess.check_output",
                   return_value=ffprobe_json), \
             patch("src.quality.post_render_validator.subprocess.run",
                   return_value=MagicMock(stderr="")):
            result = validate_video(video, expected_duration=10.0)
        assert result.has_video
        assert result.has_audio
        assert result.resolution == "1080x1920"
        assert result.duration == 10.5

    def test_validate_video_no_audio_skips_audio_analysis(self, tmp_path):
        from src.quality.post_render_validator import validate_video
        video = tmp_path / "fake.mp4"
        video.write_bytes(b"fake")
        ffprobe_json = json.dumps({
            "streams": [{"codec_type": "video", "width": 720, "height": 1280}],
            "format": {"duration": "5.0"},
        })
        with patch("src.quality.post_render_validator.subprocess.check_output",
                   return_value=ffprobe_json), \
             patch("src.quality.post_render_validator.subprocess.run",
                   return_value=MagicMock(stderr="")):
            result = validate_video(video)
        assert result.has_video
        assert not result.has_audio

    def test_format_report_pass(self):
        from src.quality.post_render_validator import format_report, ValidationResult
        r = ValidationResult(passed=True, duration=10.0, resolution="1080x1920",
                             has_audio=True, subtitle_present=True)
        report = format_report(r)
        assert "通过" in report
        assert "10.0s" in report

    def test_format_report_fail_with_issues(self):
        from src.quality.post_render_validator import format_report, ValidationResult
        r = ValidationResult(passed=False, issues=["视频文件不存在: x"])
        report = format_report(r)
        assert "未通过" in report
        assert "视频文件不存在" in report


# ========== web_searcher ==========
class TestWebSearcher:
    @pytest.mark.asyncio
    async def test_search_duckduckgo_returns_results(self):
        from src.tools import web_searcher
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "AbstractText": "敦煌是丝绸之路重镇",
            "RelatedTopics": [{"Text": "莫高窟是世界遗产"}],
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        with patch("src.tools.web_searcher.httpx.AsyncClient", return_value=mock_client):
            results = await web_searcher.search("敦煌")
        assert len(results) == 2
        assert "敦煌" in results[0]["text"]

    @pytest.mark.asyncio
    async def test_search_no_results_returns_empty(self):
        from src.tools import web_searcher
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"AbstractText": "", "RelatedTopics": []}
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        with patch("src.tools.web_searcher.httpx.AsyncClient", return_value=mock_client):
            results = await web_searcher.search("nothing")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_http_error_returns_empty(self):
        from src.tools import web_searcher
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=RuntimeError("network"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        with patch("src.tools.web_searcher.httpx.AsyncClient", return_value=mock_client):
            results = await web_searcher.search("x")
        assert results == []

    @pytest.mark.asyncio
    async def test_batch_search_aggregates(self):
        from src.tools import web_searcher

        async def mock_search(query, max_results=5):
            return [{"query": query, "text": "result"}]

        with patch.object(web_searcher, "search", mock_search):
            results = await web_searcher.batch_search(["q1", "q2"])
        assert len(results) == 2


# ========== remotion_renderer ==========
class TestRemotionRenderer:
    def test_render_success_moves_input_to_project_dir(self, tmp_path):
        from src.tools.remotion_renderer import RemotionRenderer
        renderer = RemotionRenderer(remotion_dir=tmp_path / "remotion", fps=30)
        (tmp_path / "remotion").mkdir()
        output_path = tmp_path / "projects" / "test" / "output" / "final.mp4"
        with patch("shutil.which", return_value="/fake/npx"), \
             patch("src.tools.remotion_renderer.subprocess.run", return_value=MagicMock(returncode=0)):
            result = renderer.render({"title": "t", "titleDuration": 2.0, "segments": []}, output_path)
        # input 文件移到项目目录
        assert (tmp_path / "projects" / "test" / "remotion_input.json").exists()
        # remotion 目录无遗留 input_*.json
        assert not list((tmp_path / "remotion").glob("input_*.json"))

    def test_render_failure_deletes_input_and_raises(self, tmp_path):
        import subprocess as sp
        from src.tools.remotion_renderer import RemotionRenderer
        renderer = RemotionRenderer(remotion_dir=tmp_path / "remotion", fps=30)
        (tmp_path / "remotion").mkdir()

        def mock_run(*a, **kw):
            raise sp.CalledProcessError(1, "npx", stderr="render error")

        with patch("shutil.which", return_value="/fake/npx"), \
             patch("src.tools.remotion_renderer.subprocess.run", side_effect=mock_run):
            with pytest.raises(RuntimeError, match="Remotion 渲染失败"):
                renderer.render({"title": "t", "titleDuration": 2.0, "segments": []}, tmp_path / "out.mp4")
        # 失败时清理临时 input
        assert not list((tmp_path / "remotion").glob("input_*.json"))

    def test_render_no_npx_raises(self, tmp_path):
        from src.tools.remotion_renderer import RemotionRenderer
        renderer = RemotionRenderer(remotion_dir=tmp_path / "remotion", fps=30)
        (tmp_path / "remotion").mkdir()
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="npx 未找到"):
                renderer.render({"title": "t", "titleDuration": 2.0, "segments": []}, tmp_path / "out.mp4")

