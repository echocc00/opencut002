"""运行教培视频生产管道 - 使用辅学有道素材 + MiniMax AI"""
import asyncio
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers.provider_registry import auto_register_from_env, get_provider
from src.orchestrator.engine import PipelineEngine
from src.orchestrator.state import ProjectState, StageStatus
from src.agents.skill_loader import SkillLoader
from src.agents.decision_logger import DecisionLogger
from src.providers.selector import ProviderSelector
from src.config import DomainConfig

async def main():
    # 1. 注册Provider
    print("=== 1. 注册MiniMax Provider ===")
    ok = auto_register_from_env()
    if not ok:
        print("❌ 无法注册Provider，请检查minimax-key.txt")
        return
    print("✅ MiniMax Provider注册成功")

    # 2. 准备素材
    print("\n=== 2. 加载素材 ===")
    mat_dir = Path("data/projects/edu_test/materials")
    materials = []
    if mat_dir.exists():
        for f in sorted(mat_dir.glob("*.jpg")):
            materials.append({"file": str(f), "filename": f.name})
    print(f"✅ 加载了 {len(materials)} 张素材图片")

    # 3. 创建简化管道（跳过需要Node.js/音频文件的阶段）
    data_dir = Path("data")
    proj_dir = data_dir / "projects" / "edu_test"
    proj_dir.mkdir(parents=True, exist_ok=True)

    # 4. 初始化引擎
    print("\n=== 3. 初始化管道引擎 ===")
    eng = PipelineEngine(data_dir=data_dir)

    # 使用education领域配置
    config = DomainConfig(Path("domains/education"))
    loader = SkillLoader(config)
    selector = ProviderSelector()
    logger = DecisionLogger(data_dir, "edu_test")

    eng.auto_register_handlers(loader, selector, logger)
    print(f"✅ 注册了 {len(eng.stage_handlers)} 个handler")

    # 5. 创建项目状态
    state = ProjectState(
        project_id="edu_test",
        domain="education",
        approval_mode="full_auto",
        materials=materials,
    )

    # 注入material_analysis的输入
    ma_stage = state.get_stage("material_analysis")
    ma_stage.input_data = {"materials": materials}

    # 6. 修改管道：只跑到storyboard（跳过tts/render等需要文件系统的阶段）
    import yaml
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

    # 7. 运行管道
    print("\n=== 4. 运行管道（全自动模式）===")
    print("这可能需要几分钟...")
    try:
        await eng.run(state)
    except Exception as e:
        print(f"管道运行出错: {e}")
        import traceback
        traceback.print_exc()

    # 8. 输出结果
    print("\n=== 5. 管道结果 ===")
    for stage_def in eng.get_stages():
        name = stage_def["name"]
        stage = state.get_stage(name)
        status = stage.status.value if stage.status else "unknown"
        confidence = stage.confidence_score
        icon = "✅" if status == "completed" else "❌" if status == "error" else "⏳"
        print(f"  {icon} {name:20s} {status:12s} confidence={confidence}")

    # 9. 展示关键产出
    print("\n=== 6. 关键产出 ===")

    topic = state.get_stage_output("topic")
    if topic and topic.get("directions"):
        print("\n📋 选题方向:")
        for i, d in enumerate(topic["directions"]):
            print(f"  {i+1}. {d.get('name','')} (hook={d.get('hook','')})")
            print(f"     理由: {d.get('why_work','')}")

    hl = state.get_stage_output("highlight_selection")
    if hl and hl.get("options"):
        sel = hl.get("selected", 0)
        if 0 <= sel < len(hl["options"]):
            opt = hl["options"][sel]
            print(f"\n💡 选中亮点: {', '.join(opt.get('highlight_names',[]))}")
            print(f"   呈现方式: {opt.get('presentation_style','')}")

    cw = state.get_stage_output("copywriting")
    if cw and cw.get("paragraphs"):
        print(f"\n📝 文案 ({len(cw['paragraphs'])}段, tone={cw.get('tone','')}):")
        for i, p in enumerate(cw["paragraphs"]):
            print(f"  {i+1}. [{p.get('emotion_tone','')}] {p.get('text','')}")
            print(f"     图片: {p.get('image_hint','')} | 亮点: {p.get('highlight_ref','')}")

    sb = state.get_stage_output("storyboard")
    if sb and sb.get("segments"):
        print(f"\n🎬 分镜 ({len(sb['segments'])}段, 总时长{sb.get('total_duration',0):.1f}s):")
        for seg in sb["segments"]:
            print(f"  {seg.get('index',0)}. {seg.get('image','')} ({seg.get('actual_duration',0):.1f}s) 字幕: {seg.get('subtitle','')[:30]}")

    title = state.get_stage_output("title")
    if title and title.get("titles"):
        print(f"\n📰 标题候选:")
        for t in title["titles"]:
            print(f"  - {t}")

    # 10. 保存状态
    state.save(data_dir)
    print(f"\n✅ 状态已保存到 data/projects/edu_test/state.json")

    # 11. 决策日志
    logs = logger.get_all()
    print(f"\n📊 决策日志: {len(logs)} 条记录")
    for log in logs:
        print(f"  {log.get('stage',''):20s} provider={log.get('provider','')} confidence={log.get('confidence',0)}")

if __name__ == "__main__":
    asyncio.run(main())
