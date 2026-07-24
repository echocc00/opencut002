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
from src.tools.material_prep import DIVERSITY_MAX_PER_VIDEO, diversity_enabled, prepare_materials


async def main(full: bool = False, materials_dir: str = "data/projects/edu_test/materials",
               project_id: str = "edu_test", domain: str = "education",
               script_file: str | None = None, pipeline: str | None = None):
    if not auto_register_from_env():
        print("❌ 未配置 Provider：请设置 MINIMAX_API_KEY 环境变量（或保留 ../minimax-key.txt）")
        sys.exit(1)
    print("✅ Provider OK")

    mat_dir = Path(materials_dir)
    if not mat_dir.exists():
        print(f"❌ 素材目录不存在: {mat_dir}（放入 .jpg/.jpeg/.png 图片，或 .mp4 等视频自动抽帧）")
        sys.exit(1)
    # OPENCUT_MATERIAL_DIVERSITY=1: 帧间差异选帧 + 每视频最多 3 帧（v0.6.4，避免候选都是首帧）
    _div = diversity_enabled()
    materials = prepare_materials(
        mat_dir,
        max_per_video=DIVERSITY_MAX_PER_VIDEO if _div else None,
        diversity=_div,
    )
    if not materials:
        print(f"❌ 素材目录无可用图片/视频: {mat_dir}（支持 jpg/jpeg/png + mp4/mov/avi/mkv/webm）")
        sys.exit(1)
    print(f"✅ {len(materials)}张素材（支持 jpg/jpeg/png + 视频自动抽帧）")

    data_dir = Path("data")
    if pipeline:
        # --pipeline <name>：直接加载 pipelines/<name>.yaml（minimal/draft/topic_first/default/script_first）
        eng = PipelineEngine(data_dir=data_dir, pipeline_file=f"pipelines/{pipeline}.yaml")
        mode = f"pipeline={pipeline}"
    elif script_file:
        eng = PipelineEngine(data_dir=data_dir, pipeline_file="pipelines/script_first.yaml")
        mode = "script-first（文案驱动，跳过选题/亮点/AI 文案）"
    else:
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
    config = DomainConfig(Path(f"domains/{domain}"))
    eng.auto_register_handlers(SkillLoader(config), ProviderSelector(), DecisionLogger(data_dir, project_id))

    from src.orchestrator.state import StageStatus
    state = ProjectState.load(data_dir, project_id)
    if state is None:
        state = ProjectState(project_id=project_id, domain=domain, approval_mode="full_auto", materials=materials)
    else:
        done = sum(1 for s in state.stages.values() if s.status == StageStatus.COMPLETED)
        print(f"📂 恢复已有状态（{done} 阶段已完成），重试未完成阶段")
        # 重置 pending/error 阶段的 retry_count，给重试机会
        for st in state.stages.values():
            if st.status in (StageStatus.PENDING, StageStatus.ERROR):
                st.status = StageStatus.PENDING
                st.retry_count = 0
                st.error = None
    state.get_stage("material_analysis").input_data = {"materials": materials}

    # 文案驱动模式：覆盖 copywriting handler + 注入用户文案
    if script_file:
        from src.agents.script_input_agent import ScriptInputAgent
        script_text = Path(script_file).read_text(encoding="utf-8")
        script_agent = ScriptInputAgent(SkillLoader(config), ProviderSelector(), DecisionLogger(data_dir, project_id))
        eng.register_handler("copywriting", script_agent.execute)
        state.get_stage("copywriting").input_data = {"user_script": script_text}
        print(f"✅ 文案驱动：已加载用户文案（{len(script_text)} 字）")

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
    parser.add_argument("--materials-dir", default="data/projects/edu_test/materials",
                        help="素材目录（图片 jpg/jpeg/png，或视频 mp4/mov/avi/mkv/webm 自动抽帧）")
    parser.add_argument("--project-id", default="edu_test", help="项目 ID（输出到 data/projects/{id}/）")
    parser.add_argument("--domain", default="education", help="领域（travel/education/knowledge_paid/custom）")
    parser.add_argument("--script-file", default=None,
                        help="文案驱动模式：提供文案文件路径，跳过选题/亮点/AI文案，自动匹配素材池")
    parser.add_argument("--pipeline", default=None,
                        help="指定 pipeline 变体（minimal/draft/topic_first/default/script_first）。"
                             "minimal 需配合 --script-file；draft/topic_first 需 --full")
    args = parser.parse_args()
    asyncio.run(main(full=args.full, materials_dir=args.materials_dir,
                     project_id=args.project_id, domain=args.domain,
                     script_file=args.script_file, pipeline=args.pipeline))
