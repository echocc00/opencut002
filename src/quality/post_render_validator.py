"""渲染后质量自检 - ffprobe + 帧采样 + 音频分析"""
from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ValidationResult:
    passed: bool = False
    checks: dict[str, bool] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration: float = 0.0
    resolution: str = ""
    has_audio: bool = False
    has_video: bool = False
    black_frames_detected: int = 0
    has_silence: bool = False
    has_clipping: bool = False
    peak_db: float = 0.0
    rms_db: float = 0.0
    subtitle_present: bool = False


CRITICAL_CHECKS = ["video_stream_present", "duration_positive", "no_all_black_frames", "no_sustained_silence"]
WARNING_CHECKS = ["audio_level_healthy", "subtitle_present", "no_clipping"]


def validate_video(video_path: str | Path, expected_duration: Optional[float] = None,
                   ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe") -> ValidationResult:
    """运行全部质量检查"""
    video_path = Path(video_path)
    result = ValidationResult()

    if not video_path.exists():
        result.issues.append(f"视频文件不存在: {video_path}")
        return result

    # 1. ffprobe 基础验证
    _run_ffprobe(video_path, result, ffprobe_path)

    # 2. 帧采样 - 黑帧检测
    _run_frame_sampling(video_path, result, ffmpeg_path)

    # 3. 音频分析
    if result.has_audio:
        _run_audio_analysis(video_path, result, ffmpeg_path)

    # 4. 字幕检查
    _check_subtitle(video_path, result, ffprobe_path)

    # 5. 时长验证
    if expected_duration:
        if result.duration > 0:
            deviation = abs(result.duration - expected_duration) / expected_duration
            result.checks["duration_within_tolerance"] = deviation < 0.15
            if deviation >= 0.15:
                result.issues.append(f"时长偏差 {deviation:.0%}（预期 {expected_duration:.1f}s，实际 {result.duration:.1f}s）")

    # 综合判定
    result.passed = all(result.checks.get(c, False) for c in CRITICAL_CHECKS)
    return result


def _run_ffprobe(video_path: Path, result: ValidationResult, ffprobe_path: str):
    cmd = [ffprobe_path, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(video_path)]
    try:
        output = subprocess.check_output(cmd, timeout=30)
        data = json.loads(output)
        streams = data.get("streams", [])
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

        result.has_video = len(video_streams) > 0
        result.has_audio = len(audio_streams) > 0

        if video_streams:
            vs = video_streams[0]
            result.resolution = f"{vs.get('width', 0)}x{vs.get('height', 0)}"

        result.duration = float(data.get("format", {}).get("duration", 0))
        result.checks["video_stream_present"] = result.has_video
        result.checks["duration_positive"] = result.duration > 0.5
    except Exception as e:
        result.issues.append(f"ffprobe 分析失败: {e}")
        result.checks["video_stream_present"] = False
        result.checks["duration_positive"] = False


def _run_frame_sampling(video_path: Path, result: ValidationResult, ffmpeg_path: str):
    positions = [0.25, 0.50, 0.75, 0.95]
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, pos in enumerate(positions):
            seek = result.duration * pos if result.duration > 0 else 0
            out = Path(tmpdir) / f"frame_{i}.png"
            cmd = [ffmpeg_path, "-y", "-ss", str(seek), "-i", str(video_path), "-vframes", "1", "-q:v", "2", str(out)]
            try:
                subprocess.run(cmd, capture_output=True, timeout=15, check=True)
                # 用 signalstats 检测亮度
                detect = [ffmpeg_path, "-i", str(out), "-vf", "signalstats", "-f", "null", "-"]
                det_out = subprocess.run(detect, capture_output=True, text=True, timeout=15)
                for line in det_out.stderr.split("\n"):
                    if "YAVG" in line:
                        try:
                            yavg = float(line.split("YAVG:")[-1].strip().split()[0])
                            if yavg < 10:
                                result.black_frames_detected += 1
                        except (ValueError, IndexError):
                            pass
            except subprocess.CalledProcessError:
                pass

    result.checks["no_all_black_frames"] = result.black_frames_detected < 3


def _run_audio_analysis(video_path: Path, result: ValidationResult, ffmpeg_path: str):
    cmd = [ffmpeg_path, "-i", str(video_path), "-af", "volumedetect", "-f", "null", "-"]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=60)
        for line in output.split("\n"):
            if "mean_volume" in line:
                try:
                    result.rms_db = float(line.split(":")[-1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
            if "max_volume" in line:
                try:
                    result.peak_db = float(line.split(":")[-1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
        result.has_silence = result.rms_db < -40
        result.has_clipping = result.peak_db > -0.5
        result.checks["no_sustained_silence"] = not result.has_silence
        result.checks["audio_level_healthy"] = -20 <= result.rms_db <= -3
        result.checks["no_clipping"] = not result.has_clipping
    except subprocess.CalledProcessError:
        result.issues.append("音频分析失败")


def _check_subtitle(video_path: Path, result: ValidationResult, ffprobe_path: str):
    cmd = [ffprobe_path, "-v", "quiet", "-print_format", "json", "-show_streams", str(video_path)]
    try:
        output = subprocess.check_output(cmd, timeout=15)
        data = json.loads(output)
        sub_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "subtitle"]
        result.subtitle_present = len(sub_streams) > 0
        result.checks["subtitle_present"] = result.subtitle_present
    except Exception:
        result.checks["subtitle_present"] = False


def format_report(result: ValidationResult) -> str:
    lines = ["=" * 50, "视频质量验证报告", "=" * 50, ""]
    status = "通过" if result.passed else "未通过"
    lines.append(f"总体判定: {status}")
    lines.append(f"时长: {result.duration:.1f}s | 分辨率: {result.resolution}")
    lines.append(f"音频: {'有' if result.has_audio else '无'} | 字幕: {'有' if result.subtitle_present else '无'}")
    lines.append("")
    lines.append("--- Critical Checks ---")
    labels = {
        "video_stream_present": "视频流存在", "duration_positive": "时长大于 0.5 秒",
        "no_all_black_frames": f"无大量黑帧（检测到 {result.black_frames_detected} 帧）",
        "no_sustained_silence": "无持续静音",
    }
    for c in CRITICAL_CHECKS:
        passed = result.checks.get(c, False)
        lines.append(f"  {'✅' if passed else '❌'} {labels.get(c, c)}")
    lines.append("")
    lines.append("--- Warning Checks ---")
    wlabels = {
        "audio_level_healthy": f"音频电平正常（RMS: {result.rms_db:.1f}dB）",
        "subtitle_present": "字幕存在", "no_clipping": "无削波",
    }
    for c in WARNING_CHECKS:
        passed = result.checks.get(c, False)
        lines.append(f"  {'✅' if passed else '⚠️'} {wlabels.get(c, c)}")
    if result.issues:
        lines.append("")
        lines.append("--- 发现的问题 ---")
        for issue in result.issues:
            lines.append(f"  ❌ {issue}")
    lines.append("")
    lines.append("=" * 50)
    return "\n".join(lines)
