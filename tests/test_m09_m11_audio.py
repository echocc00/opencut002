"""M09+M11 验收测试: WhisperX转录 + FFmpeg音频处理"""
import tempfile
import subprocess
from pathlib import Path

import pytest

from src.tools.transcriber import Transcriber, TranscriptionResult
from src.tools.audio_processor import AudioProcessor


# ========== M09: Transcriber ==========

class TestTranscriber:
    def test_fallback_transcription(self):
        """Fallback 模式：能从音频生成时间戳（无文字识别）"""
        with tempfile.TemporaryDirectory() as tmp:
            # 生成 3 秒测试音频
            audio = Path(tmp) / "test.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                 "-c:a", "pcm_s16le", str(audio)],
                capture_output=True, check=True,
            )
            t = Transcriber(device="cpu")
            result = t.transcribe(audio)
            assert result.method == "fallback"
            assert len(result.words) > 0
            assert result.words[0]["start"] >= 0.0
            assert result.words[-1]["end"] <= 3.5

    def test_transcription_result_to_dict(self):
        result = TranscriptionResult(
            full_text="测试文字",
            words=[{"word": "测试", "start": 0.0, "end": 0.5}],
            method="whisperx",
        )
        d = result.to_dict()
        assert d["full_text"] == "测试文字"
        assert d["word_timestamps"][0]["word"] == "测试"
        assert d["method"] == "whisperx"

    def test_transcriber_missing_file(self):
        t = Transcriber()
        with pytest.raises(FileNotFoundError):
            t.transcribe("/nonexistent/audio.wav")

    def test_fallback_word_timestamps_in_range(self):
        """Fallback 时间戳在音频时长范围内"""
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "test.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
                 "-c:a", "pcm_s16le", str(audio)],
                capture_output=True, check=True,
            )
            t = Transcriber(device="cpu")
            result = t.transcribe(audio)
            for w in result.words:
                assert 0.0 <= w["start"] <= 5.5
                assert w["end"] >= w["start"]


# ========== M11: AudioProcessor ==========

class TestAudioProcessor:
    @pytest.fixture
    def audio_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            voice = Path(tmp) / "voice.wav"
            bgm = Path(tmp) / "bgm.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                 "-c:a", "pcm_s16le", str(voice)],
                capture_output=True, check=True,
            )
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=110:duration=5",
                 "-c:a", "pcm_s16le", str(bgm)],
                capture_output=True, check=True,
            )
            yield {"voice": voice, "bgm": bgm, "tmp": tmp}

    def test_mix_bgm_with_ducking(self, audio_files):
        """BGM + 语音混音成功输出"""
        output = Path(audio_files["tmp"]) / "mixed.wav"
        ap = AudioProcessor()
        result = ap.mix_bgm_with_ducking(
            audio_files["voice"], audio_files["bgm"], output,
            bgm_volume=0.25,
        )
        assert Path(result).exists()
        # 输出时长应该匹配语音时长
        import json
        probe = json.loads(subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", result]
        ))
        duration = float(probe["format"]["duration"])
        assert 2.5 <= duration <= 3.5

    def test_normalize_audio(self, audio_files):
        """音量归一化成功"""
        output = Path(audio_files["tmp"]) / "normalized.wav"
        ap = AudioProcessor()
        result = ap.normalize_audio(audio_files["voice"], output, target_rms=-16.0)
        assert Path(result).exists()

    def test_detect_clipping(self, audio_files):
        """削波检测返回正确的音频电平信息"""
        ap = AudioProcessor()
        info = ap.detect_clipping(audio_files["voice"])
        assert "rms_db" in info
        assert "peak_db" in info
        assert "has_clipping" in info
        assert "has_silence" in info
        assert "is_healthy" in info
        # 正弦波不应该有削波
        assert not info["has_clipping"]

    def test_detect_clipping_on_clipped_audio(self):
        """削波音频被正确检测"""
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "clipped.wav"
            # 生成高音量音频（可能削波）
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                 "-af", "volume=10.0", "-c:a", "pcm_s16le", str(audio)],
                capture_output=True, check=True,
            )
            ap = AudioProcessor()
            info = ap.detect_clipping(audio)
            assert info["peak_db"] > -1.0  # 接近或超过 0dB
