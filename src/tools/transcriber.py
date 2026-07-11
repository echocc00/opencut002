"""WhisperX 转录管道 - 词级时间戳

优先使用 WhisperX（需CUDA），无GPU时fallback到基于ffmpeg的静音分段估算。
"""
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class TranscriptionResult:
    def __init__(self, full_text: str = "", words: list[dict] = None,
                 segments: list[dict] = None, method: str = "fallback"):
        self.full_text = full_text
        self.words = words or []
        self.segments = segments or []
        self.method = method

    def to_dict(self) -> dict[str, Any]:
        return {
            "full_text": self.full_text,
            "word_timestamps": self.words,
            "segments": self.segments,
            "method": self.method,
        }


class Transcriber:
    def __init__(self, model_name: str = "base", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._whisperx_model = None

    def transcribe(self, audio_path: str | Path, language: str = "zh", known_text: str = "") -> TranscriptionResult:
        """转录音频，返回词级时间戳。known_text用于fallback时回填word字段。"""
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        if self.device != "cpu" or self._try_whisperx():
            try:
                return self._transcribe_whisperx(audio_path, language)
            except Exception as e:
                log.warning(f"WhisperX 转录失败，使用 fallback: {e}")

        return self._transcribe_fallback(audio_path, language, known_text=known_text)

    def _try_whisperx(self) -> bool:
        try:
            import whisperx  # noqa: F401
            return True
        except ImportError:
            return False

    def _transcribe_whisperx(self, audio_path: Path, language: str) -> TranscriptionResult:
        import whisperx
        if self._whisperx_model is None:
            self._whisperx_model = whisperx.load_model(self.model_name, self.device)
        audio = whisperx.load_audio(str(audio_path))
        result = self._whisperx_model.transcribe(audio, language=language)
        try:
            model_a, metadata = whisperx.load_align_model(language_code=language, device=self.device)
            result = whisperx.align(result["segments"], model_a, metadata, audio, self.device)
        except Exception as e:
            log.warning(f"词级对齐失败: {e}")
        words: list[dict] = []
        for seg in result.get("segments", []):
            for w in seg.get("words", []):
                words.append({"word": w.get("word", "").strip(), "start": w.get("start", 0.0), "end": w.get("end", 0.0)})
        return TranscriptionResult(
            full_text=" ".join(seg.get("text", "") for seg in result.get("segments", [])),
            words=words, segments=result.get("segments", []), method="whisperx",
        )

    def _transcribe_fallback(self, audio_path: Path, language: str, known_text: str = "") -> TranscriptionResult:
        """Fallback: 用 ffmpeg silencedetect 估算分段时间戳，已知文本回填word字段"""
        cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(audio_path)]
        probe = json.loads(subprocess.check_output(cmd, timeout=15))
        duration = float(probe.get("format", {}).get("duration", 0))

        silence_cmd = ["ffmpeg", "-i", str(audio_path), "-af", "silencedetect=noise=-30dB:d=0.3", "-f", "null", "-"]
        output = subprocess.run(silence_cmd, capture_output=True, text=True, timeout=60)

        silence_starts: list[float] = []
        silence_ends: list[float] = []
        for line in output.stderr.split("\n"):
            if "silence_start" in line:
                try: silence_starts.append(float(line.split("silence_start:")[1].strip().split()[0]))
                except (ValueError, IndexError): pass
            if "silence_end" in line:
                try: silence_ends.append(float(line.split("silence_end:")[1].strip().split()[0]))
                except (ValueError, IndexError): pass

        segments: list[dict] = []
        if silence_starts and silence_ends:
            if silence_starts[0] > 0.1:
                segments.append({"start": 0.0, "end": silence_starts[0]})
            for i in range(len(silence_ends) - 1):
                segments.append({"start": silence_ends[i], "end": silence_starts[i + 1]})
            if silence_ends and silence_ends[-1] < duration:
                segments.append({"start": silence_ends[-1], "end": duration})
        else:
            segments.append({"start": 0.0, "end": duration})

        # #15 修复：已知文本按字符切分回填
        words: list[dict] = []
        all_chars = list(known_text.replace(" ", "").replace("\n", "")) if known_text else []
        total_seg_duration = sum(s["end"] - s["start"] for s in segments)

        if all_chars and total_seg_duration > 0:
            char_duration = total_seg_duration / len(all_chars)
            char_idx = 0
            for seg in segments:
                seg_dur = seg["end"] - seg["start"]
                chars_in_seg = max(1, int(seg_dur / char_duration))
                for i in range(chars_in_seg):
                    if char_idx >= len(all_chars):
                        break
                    start = seg["start"] + i * (seg_dur / chars_in_seg)
                    words.append({"word": all_chars[char_idx], "start": start, "end": start + (seg_dur / chars_in_seg)})
                    char_idx += 1
        else:
            for seg in segments:
                seg_duration = seg["end"] - seg["start"]
                est_chars = max(1, int(seg_duration / 0.3))
                char_duration = seg_duration / est_chars
                for i in range(est_chars):
                    words.append({"word": "", "start": seg["start"] + i * char_duration, "end": seg["start"] + (i + 1) * char_duration})

        return TranscriptionResult(
            full_text=known_text, words=words, segments=segments, method="fallback",
        )
