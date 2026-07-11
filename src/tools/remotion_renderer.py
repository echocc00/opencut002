"""Remotion 渲染管道 - Python 调用 Remotion CLI 渲染视频"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class RemotionRenderer:
    def __init__(self, remotion_dir: str | Path = "remotion", fps: int = 30):
        self.remotion_dir = Path(remotion_dir)
        self.fps = fps

    def render(self, project_data: dict[str, Any], output_path: str | Path,
               duration_frames: int | None = None) -> str:
        """渲染视频

        Args:
            project_data: 视频数据（标题、段落、音频路径、样式等）
            output_path: 输出 MP4 路径
            duration_frames: 总帧数（如不指定则根据段落时长计算）
        """
        output_path = Path(output_path)

        # 计算总帧数
        if duration_frames is None:
            total_duration = sum(
                seg.get("actual_duration", 3.0) for seg in project_data.get("segments", [])
            )
            title_dur = project_data.get("titleDuration", 0)
            duration_frames = int((total_duration + title_dur) * self.fps)

        # 写入输入数据文件
        import uuid
        input_file = self.remotion_dir / f"input_{uuid.uuid4().hex}.json"
        input_file.parent.mkdir(parents=True, exist_ok=True)
        input_file.write_text(json.dumps(project_data, ensure_ascii=False), encoding="utf-8")

        # 构建 Remotion CLI 命令
        cmd = [
            "npx", "remotion", "render",
            "VideoComposition",
            str(output_path),
            "--props", str(input_file),
            "--codec", "h264",
            "--fps", str(self.fps),
            "--frames", str(duration_frames),
        ]

        log.info(f"Rendering video: {output_path} ({duration_frames} frames)")
        subprocess.run(cmd, cwd=str(self.remotion_dir), check=True, timeout=600)
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
                elif k == "transition_duration": camel_key = "transitionDuration"
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
        }
