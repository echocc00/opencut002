"""R01 渲染冒烟测试 - 直接调用 RemotionRenderer 验证逐词字幕 + 封面 + domain 接线。

绕过管道质量关卡，用预设分镜数据验证 Python -> Remotion -> mp4 通路。
用法: python scripts/render_smoke.py
"""
import sys, os, json
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from src.tools.remotion_renderer import RemotionRenderer


def main():
    # 2 段分镜：累积 time_start，带逐词时间戳（模拟 tts word_timestamps 对齐后）
    segments = [
        {"index": 0, "image": "images/img_01.jpg", "actual_duration": 3.5, "time_start": 0.0,
         "subtitle": "辅学有道，开启智慧之旅",
         "subtitle_words": [
             {"word": "辅学有道", "start": 0.0, "end": 0.8},
             {"word": "开启", "start": 0.9, "end": 1.3},
             {"word": "智慧之旅", "start": 1.4, "end": 2.5},
         ],
         "transition": "fade"},
        {"index": 1, "image": "images/img_02.jpg", "actual_duration": 3.0, "time_start": 3.5,
         "subtitle": "让学习更高效",
         "subtitle_words": [
             {"word": "让学习", "start": 0.0, "end": 0.7},
             {"word": "更高效", "start": 0.8, "end": 1.5},
         ],
         "transition": "slide"},
    ]

    render_data = RemotionRenderer.build_render_data(
        title="辅学有道", title_duration=2.0,
        segments=segments,
        voice_path="audio/voice.wav",
        bgm_path="audio/ambient.mp3",
        bgm_volume=0.2,
        cover_image="images/img_03.jpg",
        domain="education",
    )

    print("=== render_data (camelCase 边界) ===")
    print(json.dumps(render_data, ensure_ascii=False, indent=2)[:900])

    output_path = "data/projects/render_smoke/output/final.mp4"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    renderer = RemotionRenderer(remotion_dir="remotion", fps=30)
    print(f"\n=== rendering to {output_path} (首次 bundling 可能 1-2 分钟) ===")
    renderer.render(render_data, output_path)

    p = Path(output_path)
    if p.exists() and p.stat().st_size > 0:
        print(f"\n✅ 渲染成功: {output_path} ({p.stat().st_size/1024:.0f} KB)")
        print("   验证点: coverImage/domain 已传入、subtitleWords camelCase、逐词字幕数据流接通")
    else:
        print(f"\n❌ 渲染失败: 输出不存在或为空")
        sys.exit(1)


if __name__ == "__main__":
    main()
