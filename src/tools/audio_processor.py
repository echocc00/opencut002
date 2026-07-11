"""FFmpeg 音频处理 - BGM混音+ducking+归一化+削波检测"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


class AudioProcessor:
    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        self.ffmpeg = ffmpeg_path
        self.ffprobe = ffprobe_path

    def mix_bgm_with_ducking(
        self, voice_path: str | Path, bgm_path: str | Path,
        output_path: str | Path,
        bgm_volume: float = 0.25,
        duck_threshold: float = 0.05,
    ) -> str:
        """BGM + 语音混音，语音段自动降低 BGM 音量"""
        voice_path = Path(voice_path)
        bgm_path = Path(bgm_path)
        output_path = Path(output_path)
        voice_duration = self._get_duration(voice_path)

        filter_complex = (
            f"[1:a]atrim=duration={voice_duration},volume={bgm_volume},"
            f"aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=mono[bgm];"
            "[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=mono[voice];"
            f"[bgm][voice]sidechaincompress=threshold={duck_threshold}:ratio=4:"
            f"attack=0.05:release=0.5[ducked];"
            "[ducked][0:a]amix=inputs=2:duration=first[aout]"
        )
        cmd = [
            self.ffmpeg, "-y",
            "-i", str(voice_path), "-i", str(bgm_path),
            "-filter_complex", filter_complex,
            "-map", "[aout]", "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, timeout=120, check=True)
        return str(output_path)

    def normalize_audio(self, input_path: str | Path, output_path: str | Path,
                        target_rms: float = -16.0) -> str:
        """音量归一化到目标 RMS"""
        cmd = [
            self.ffmpeg, "-y", "-i", str(input_path),
            "-af", f"loudnorm=I={target_rms}:TP=-1.5:LRA=11",
            "-c:a", "aac", "-b:a", "192k", str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, timeout=60, check=True)
        return str(output_path)

    def detect_clipping(self, audio_path: str | Path) -> dict[str, Any]:
        """检测削波和音频电平"""
        cmd = [self.ffmpeg, "-i", str(audio_path), "-af", "volumedetect", "-f", "null", "-"]
        output = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        rms_db = 0.0
        peak_db = 0.0
        for line in output.stderr.split("\n"):
            if "mean_volume" in line:
                try: rms_db = float(line.split(":")[-1].strip().split()[0])
                except (ValueError, IndexError): pass
            if "max_volume" in line:
                try: peak_db = float(line.split(":")[-1].strip().split()[0])
                except (ValueError, IndexError): pass
        return {
            "rms_db": rms_db, "peak_db": peak_db,
            "has_clipping": peak_db > -0.5, "has_silence": rms_db < -40,
            "is_healthy": -20 <= rms_db <= -3,
        }

    def _get_duration(self, audio_path: Path) -> float:
        cmd = [self.ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", str(audio_path)]
        try:
            data = json.loads(subprocess.check_output(cmd, timeout=15))
            return float(data.get("format", {}).get("duration", 0))
        except Exception:
            return 0.0
