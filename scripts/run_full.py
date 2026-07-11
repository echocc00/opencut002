"""OpenCut v3 管道运行入口

默认（无参数）：12 阶段冒烟测试，跳过 tts/render（不需 ffmpeg/node）。
--full：完整 20 阶段管道，含 tts+render，验证渲染路径（需 minimax key + ffmpeg + node）。
"""
import argparse, asyncio, sys, os, yaml
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows 控制台默认 GBK，emoji/中文会 UnicodeEncodeError；强制 UTF-8 输出
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from src.providers.provider_registry import auto_register_from_env
from src.orchestrator.engine import PipelineEngine
from src.orchestrator.state import ProjectState
from src.agents.skill_loader import SkillLoader
from src.agents.decision_logger import DecisionLogger
from src.providers.selector import ProviderSelector
from src.config import DomainConfig


async def main(full: bool = False):
    if not auto_register_from_env():
        print("❌ 未配置 Provider：请设置 MINIMAX_API_KEY 环境变量（或保留 ../minimax-key.txt）")
        sys.exit(1)
    print("✅ Provider OK")

    mat_dir = Path("data/projects/edu_test/materials")
    if not mat_dir.exists():
        print(f"❌ 素材目录不存在: {mat_dir}（需放入 .jpg 素材）")
        sys.exit(1)
    materials = [{"file": str(f), "filename": f.name} for f in sorted(mat_dir.glob("*.jpg"))][:5]
    print(f"✅ {len(materials)}张素材")

    data_dir = Path("data")
    eng = PipelineEngine(data_dir=data_dir, pipeline_file="pipelines/default.yaml")

    if full:
        # 完整 20 阶段（含 tts/render，走 pipelines/default.yaml）
        mode = "full（20 阶段，真实 tts+render）"
    else:
        # 简化 12 阶段（跳过 tts/render 需要文件系统的阶段）
        pipeline_file = data_dir / "edu_pipeline.yaml"
        stages = [
            {"name": "material_analysis", "type": "auto", "requires": []},
            {"name": "web_research", "type": "auto", "requires": ["material_analysis"]},
            {"name": "topic", "type": "decision", "requires": ["material_analysis", "web_research"]},
            {"name": "highlight_selection", "type": "decision", "requires": ["topic"]},
            {"name": "copywriting", "type": "decision", "requires": ["topic", "highlight_selection"]},
            {"name": "image_matching", "type": "auto", "requires": ["copywriting", "material_analysis"]},
            {"name": "voice_selection", "type": "decision", "requires": ["copywriting"]},
            {"name": "storyboard", "type": "decision", "requires": ["copywriting", "image_matching"]},
            {"name": "bgm", "type": "decision", "requires": ["storyboard"]},
            {"name": "rhythm", "type": "auto", "requires": ["storyboard", "bgm"]},
            {"name": "title", "type": "decision", "requires": ["copywriting"]},
            {"name": "cover", "type": "decision", "requires": ["storyboard"]},
        ]
        pipeline_file.write_text(yaml.dump({"pipeline": {"name": "edu", "stages": stages}}), encoding="utf-8")
        eng.pipeline = eng._load_pipeline(str(pipeline_file))
        mode = "smoke（12 阶段，跳过 tts/render）"

    print(f"模式: {mode}")
    config = DomainConfig(Path("domains/education"))
    eng.auto_register_handlers(SkillLoader(config), ProviderSelector(), DecisionLogger(data_dir, "edu_test"))

    state = ProjectState(project_id="edu_test", domain="education", approval_mode="full_auto", materials=materials)
    state.get_stage("material_analysis").input_data = {"materials": materials}

    # web_search mock（避免网络抖动，--full 也不验证搜索能力）
    async def mock_search(*a, **kw):
        return [{"query": "教培", "text": "辅学有道学霸训练营提升学习效率"}]
    patch("src.agents.web_research_agent.batch_search", new=mock_search).start()

    print("运行管道...")
    try:
        await eng.run(state)
        print("\n=== 管道完成 ===")
    except Exception as e:
        print(f"\n=== 管道出错: {e} ===")

    # 输出各阶段状态
    for s in eng.get_stages():
        name = s["name"]
        st = state.get_stage(name)
        icon = "✅" if st.status.value == "completed" else "❌"
        print(f"  {icon} {name}: {st.status.value} conf={st.confidence_score}")

    render = state.get_stage_output("render")
    if render and render.get("video_path"):
        print(f"\n🎬 视频产出: {render['video_path']}")

    state.save(data_dir)
    print("\n✅ 状态已保存")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenCut v3 管道运行入口")
    parser.add_argument("--full", action="store_true",
                        help="跑完整 20 阶段管道（含 tts/render，需 minimax key + ffmpeg + node）")
    args = parser.parse_args()
    asyncio.run(main(full=args.full))
