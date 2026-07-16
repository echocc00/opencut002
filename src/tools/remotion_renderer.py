"""Remotion 渲染管道 - Python 调用 Remotion CLI 渲染视频"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class RemotionRenderer:
    def __init__(self, remotion_dir: str | Path = "remotion", fps: int = 30,
                 concurrency: int | None = None):
        self.remotion_dir = Path(remotion_dir)
        self.fps = fps
        # 渲染并发线程数；None 时按 OPENCUT_RENDER_CONCURRENCY env，默认 1（不并发）
        if concurrency is not None:
            self.concurrency = max(1, concurrency)
        else:
            try:
                self.concurrency = max(1, int(os.environ.get("OPENCUT_RENDER_CONCURRENCY", "1")))
            except ValueError:
                self.concurrency = 1

    def render(self, project_data: dict[str, Any], output_path: str | Path,
               duration_frames: int | None = None) -> str:
        """渲染视频

        Args:
            project_data: 视频数据（标题、段落、音频路径、样式等）
            output_path: 输出 MP4 路径
            duration_frames: 总帧数（如不指定则根据段落时长计算）
        """
        output_path = Path(output_path).resolve()

        # 计算总帧数（render_data 已是 camelCase，读 actualDuration）
        if duration_frames is None:
            total_duration = sum(
                seg.get("actualDuration", seg.get("actual_duration", 3.0))
                for seg in project_data.get("segments", [])
            )
            title_dur = project_data.get("titleDuration", 0)
            duration_frames = int((total_duration + title_dur) * self.fps)

        # 写入输入数据文件（包 {"data": ...} 与 Root.tsx 的 props.data 结构对齐）
        import uuid
        input_file = self.remotion_dir / f"input_{uuid.uuid4().hex}.json"
        input_file.parent.mkdir(parents=True, exist_ok=True)
        input_file.write_text(json.dumps({"data": project_data}, ensure_ascii=False), encoding="utf-8")

        # 构建 Remotion CLI 命令
        # - Windows 上需解析 npx.cmd 全路径（shutil.which）
        # - --props/--frames 用 = 语法 + 绝对路径正斜杠，规避 Windows 命令行空格/反斜杠解析
        # - --frames 用区间 0-N（单值会被 Remotion 当作单帧出图）
        import shutil
        npx = shutil.which("npx")
        if npx is None:
            raise RuntimeError("npx 未找到，请确认 Node.js 已安装并在 PATH 中")
        props_path = str(input_file.resolve()).replace("\\", "/")
        out_path = str(output_path).replace("\\", "/")
        cmd = [
            npx, "remotion", "render",
            "VideoComposition",
            out_path,
            f"--props={props_path}",
            "--codec=h264",
            f"--fps={self.fps}",
            f"--concurrency={self.concurrency}",
            # 不传 --frames：让 Remotion 用 Root.tsx calculateMetadata 算的 durationInFrames 渲染全片
            # （含 cover），避免 render 端 duration 与 composition 端不一致的 off-by-one
        ]

        log.info(f"Rendering video: {output_path} ({duration_frames} frames)")
        try:
            subprocess.run(cmd, cwd=str(self.remotion_dir), check=True, timeout=600,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        except subprocess.CalledProcessError as e:
            input_file.unlink(missing_ok=True)
            stderr = (e.stderr or "")[-2000:]
            raise RuntimeError(f"Remotion 渲染失败 (exit {e.returncode}):\n{stderr}") from e
        except Exception:
            input_file.unlink(missing_ok=True)
            raise

        # 渲染成功：保留输入到项目目录（可复现），移动失败则清理临时文件
        project_dir = Path(output_path).parent.parent
        dest = project_dir / "remotion_input.json"
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            input_file.replace(dest)
        except Exception:
            input_file.unlink(missing_ok=True)

        return str(output_path)

    @staticmethod
    def build_render_data(
        title: str,
        title_duration: float,
        segments: list[dict[str, Any]],
        voice_path: str,
        bgm_path: str = "",
        bgm_volume: float = 0.25,
        style: dict[str, str] | None = None,
        cover_image: str = "",
        domain: str = "education",
        ai_label: bool = False,
    ) -> dict[str, Any]:
        """构建 Remotion 渲染数据

        重要：此方法是 Python(snake_case) -> TypeScript(camelCase) 的转换边界。
        所有字段名在此处转为 camelCase，input.json 中只出现 camelCase。
        详见 docs/data-flow-contract.md 的"Python -> Remotion 跨语言数据契约"。
        """
        default_style = {
            "activeColor": "#D4734A",
            "pastColor": "#A9A49C",
            "upcomingColor": "#78736C",
        }
        if style:
            default_style.update(style)

        # snake_case -> camelCase 转换
        camel_segments = []
        for seg in segments:
            cs = {}
            for k, v in seg.items():
                if k == "actual_duration": camel_key = "actualDuration"
                elif k == "time_start": camel_key = "timeStart"
                elif k == "subtitle_words": camel_key = "subtitleWords"
                elif k == "subtitle_lines": camel_key = "subtitleLines"
                elif k == "transition_duration": camel_key = "transitionDuration"
                elif k == "text_card": camel_key = "textCard"
                elif k == "screen_index": camel_key = "screenIndex"
                elif k == "screens_total": camel_key = "screensTotal"
                elif k == "audio_start": camel_key = "audioStart"
                elif k == "audio_duration": camel_key = "audioDuration"
                elif k == "screen_chars": camel_key = "screenChars"
                else: camel_key = k
                cs[camel_key] = v
            camel_segments.append(cs)

        return {
            "title": title,
            "titleDuration": title_duration,
            "segments": camel_segments,
            "voicePath": voice_path,
            "bgmPath": bgm_path,
            "bgmVolume": bgm_volume,
            "style": default_style,
            "coverImage": cover_image,
            "domain": domain,
            "aiLabel": ai_label,
        }
