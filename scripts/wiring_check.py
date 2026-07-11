#!/usr/bin/env python3
"""接线检查脚本 - 验证所有模块被调用、所有数据链路接通"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_orphan_modules():
    print("=== 1. 孤儿模块检查 ===")
    orphans = []
    for root, dirs, files in os.walk(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")):
        for f in files:
            if not f.endswith(".py") or f == "__init__.py":
                continue
            path = os.path.join(root, f)
            module_name = f.replace(".py", "")
            if module_name in ["config", "state", "contracts", "engine"]:
                continue
            found = False
            for root2, dirs2, files2 in os.walk(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))):
                if "__pycache__" in root2 or ".git" in root2:
                    continue
                for f2 in files2:
                    if not f2.endswith(".py") or os.path.join(root2, f2) == path:
                        continue
                    try:
                        if module_name in open(os.path.join(root2, f2), encoding="utf-8").read():
                            found = True; break
                    except: pass
                if found: break
            if not found:
                orphans.append(os.path.relpath(path, "."))
    if orphans:
        print(f"  ⚠️ 可能孤儿模块 ({len(orphans)}):")
        for o in orphans: print(f"    {o}")
    else:
        print("  ✅ 无孤儿模块")
    return orphans

def check_stage_handlers():
    print("\n=== 2. 阶段Handler检查 ===")
    import yaml, tempfile
    from pathlib import Path
    with open("pipelines/default.yaml") as f: p = yaml.safe_load(f)
    from src.orchestrator.engine import PipelineEngine
    from src.agents.skill_loader import SkillLoader
    from src.agents.decision_logger import DecisionLogger
    from src.providers.selector import ProviderSelector
    from src.config import DomainConfig
    with tempfile.TemporaryDirectory() as tmp:
        eng = PipelineEngine(data_dir=Path(tmp))
        eng.auto_register_handlers(SkillLoader(DomainConfig(Path("domains/travel"))), ProviderSelector(), DecisionLogger(Path(tmp), "test"))
        stages = p["pipeline"]["stages"]
        missing = [s["name"] for s in stages if s["name"] not in eng.stage_handlers]
        if missing:
            print(f"  ❌ 缺少handler ({len(missing)}): {missing}")
        else:
            print(f"  ✅ 全部 {len(stages)} 个阶段都有handler")
        return missing

def check_data_flow():
    print("\n=== 3. 数据流注入检查 ===")
    all_src = open("src/orchestrator/engine.py", encoding="utf-8").read() + open("src/api/project_routes.py", encoding="utf-8").read()
    injections = {
        "material_analysis": "materials",
        "highlight_selection": "highlights",
        "copywriting": "confirmed_highlights",
        "voice_selection": "available_voices",
        "bgm": "available_bgm",
    }
    missing = []
    for stage, field in injections.items():
        if field in all_src:
            print(f"  ✅ {stage}.{field}")
        else:
            print(f"  ❌ {stage}.{field} 未找到注入")
            missing.append(stage)
    return missing

def check_quality_gates():
    print("\n=== 4. 质量关卡接入检查 ===")
    src = open("src/orchestrator/engine.py", encoding="utf-8").read()
    checks = {"preflight": "check_stage_inputs", "postflight": "validate_output", "slideshow": "score_storyboard", "post_render": "validate_video"}
    issues = []
    for name, kw in checks.items():
        if kw in src:
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name} 未接入")
            issues.append(name)
    return issues

def check_dead_functions():
    print("\n=== 5. 关键函数调用检查 ===")
    all_src = ""
    for root, dirs, files in os.walk(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")):
        if "__pycache__" in root: continue
        for f in files:
            if f.endswith(".py"): all_src += open(os.path.join(root, f), encoding="utf-8").read()
    funcs = [("confidence_scorer", "calculate_confidence"), ("preference_profile", "record_decision"),
             ("annotation_store", "build_guidance_prompt"), ("approval_controller", "should_pause_for_review"),
             ("remotion_renderer", "build_render_data"), ("transcriber", "known_text")]
    issues = []
    for label, kw in funcs:
        count = all_src.count(kw)
        if count < 2:
            print(f"  ⚠️ {label}.{kw}: 只出现{count}次")
            issues.append(label)
        else:
            print(f"  ✅ {label}.{kw}: {count}次")
    return issues

def main():
    print("=" * 60)
    print("OpenCut v3.0 接线检查")
    print("=" * 60)
    issues = []
    issues.extend(check_orphan_modules())
    issues.extend(check_stage_handlers())
    issues.extend(check_data_flow())
    issues.extend(check_quality_gates())
    issues.extend(check_dead_functions())
    print("\n" + "=" * 60)
    if issues:
        print(f"❌ 发现 {len(issues)} 个问题: {issues}")
    else:
        print("✅ 全部检查通过，无接线问题")
    print("=" * 60)
    return 1 if issues else 0

if __name__ == "__main__":
    sys.exit(main())
