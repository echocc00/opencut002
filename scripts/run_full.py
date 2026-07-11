import asyncio, sys, os, json, yaml
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers.provider_registry import auto_register_from_env
from src.orchestrator.engine import PipelineEngine
from src.orchestrator.state import ProjectState
from src.agents.skill_loader import SkillLoader
from src.agents.decision_logger import DecisionLogger
from src.providers.selector import ProviderSelector
from src.config import DomainConfig

async def main():
    auto_register_from_env()
    print("✅ Provider OK")

    mat_dir = Path("data/projects/edu_test/materials")
    materials = [{"file": str(f), "filename": f.name} for f in sorted(mat_dir.glob("*.jpg"))][:5]  # 只用5张
    print(f"✅ {len(materials)}张素材")

    data_dir = Path("data")
    eng = PipelineEngine(data_dir=data_dir)
    config = DomainConfig(Path("domains/education"))
    eng.auto_register_handlers(SkillLoader(config), ProviderSelector(), DecisionLogger(data_dir, "edu_test"))

    # 简化管道（跳过tts/render需要文件系统的阶段）
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

    state = ProjectState(project_id="edu_test", domain="education", approval_mode="full_auto", materials=materials)
    state.get_stage("material_analysis").input_data = {"materials": materials}

    async def mock_search(*a, **kw):
        return [{"query": "教培", "text": "辅学有道学霸训练营提升学习效率"}]
    patch("src.agents.web_research_agent.batch_search", new=mock_search).start()

    print("运行管道（12阶段）...")
    try:
        await eng.run(state)
        print("\n=== 管道完成 ===")
    except Exception as e:
        print(f"\n=== 管道出错: {e} ===")

    # 输出结果
    for s in stages:
        name = s["name"]
        st = state.get_stage(name)
        icon = "✅" if st.status.value == "completed" else "❌"
        print(f"  {icon} {name}: {st.status.value} conf={st.confidence_score}")

    topic = state.get_stage_output("topic")
    if topic and topic.get("directions"):
        print("\n📋 选题:")
        for d in topic["directions"]:
            print(f"  - {d.get('name','')}: {d.get('hook','')}")

    hl = state.get_stage_output("highlight_selection")
    if hl and hl.get("options"):
        sel = hl.get("selected", 0)
        if 0 <= sel < len(hl["options"]):
            opt = hl["options"][sel]
            print(f"\n💡 亮点: {', '.join(opt.get('highlight_names',[]))}")
            print(f"   呈现: {opt.get('presentation_style','')}")

    cw = state.get_stage_output("copywriting")
    if cw and cw.get("paragraphs"):
        print(f"\n📝 文案({len(cw['paragraphs'])}段):")
        for i, p in enumerate(cw["paragraphs"]):
            print(f"  {i+1}. [{p.get('emotion_tone','')}] {p.get('text','')}")

    sb = state.get_stage_output("storyboard")
    if sb and sb.get("segments"):
        print(f"\n🎬 分镜({len(sb['segments'])}段, {sb.get('total_duration',0):.1f}s):")
        for seg in sb["segments"]:
            print(f"  {seg.get('index',0)}. {seg.get('image','')} ({seg.get('actual_duration',0):.1f}s)")

    title = state.get_stage_output("title")
    if title and title.get("titles"):
        print(f"\n📰 标题:")
        for t in title["titles"]:
            print(f"  - {t}")

    state.save(data_dir)
    print("\n✅ 状态已保存")

asyncio.run(main())
