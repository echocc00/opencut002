"""资产迁移工具 - 从 v2.1.0 迁移保留的资产"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def migrate_tts_voices(source_file: str | Path, target_file: str | Path) -> int:
    """迁移 TTS 音色配置"""
    source = Path(source_file)
    target = Path(target_file)
    if not source.exists():
        return 0
    # v2 格式: {"voice_key": {"name": "", "edge_tts_voice": ""}}
    # v3 格式相同，直接复制
    data = json.loads(source.read_text(encoding="utf-8"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(data)


def migrate_highlights(source_file: str | Path, target_file: str | Path) -> int:
    """迁移亮点归类库"""
    source = Path(source_file)
    target = Path(target_file)
    if not source.exists():
        return 0
    data = json.loads(source.read_text(encoding="utf-8"))
    # v3 格式: {"highlights": [...]}
    if "highlights" not in data:
        data = {"highlights": data if isinstance(data, list) else [data]}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(data.get("highlights", []))


def migrate_bgm_library(source_dir: str | Path, target_dir: str | Path) -> int:
    """迁移 BGM 曲库"""
    source = Path(source_dir)
    target = Path(target_dir)
    if not source.exists():
        return 0
    target.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in source.glob("*.mp3"):
        shutil.copy2(f, target / f.name)
        count += 1
    return count


def migrate_ffmpeg_audio_code(source_file: str | Path) -> bool:
    """检查 v2 FFmpeg 音频处理代码是否存在（供参考迁移）"""
    return Path(source_file).exists()


# v2 -> v3 阶段名映射
STAGE_NAME_MAP = {
    "image_analysis": "material_analysis",
    "voice": "voice_selection",
    "script": "copywriting",
    "scene_plan": "storyboard",
    "assets": "image_matching",
}

# v2 -> v3 字段名映射
FIELD_NAME_MAP = {
    "display_name": "name",
    "voice_key": "selected",
    "script_text": "text",
}


def migrate_pipeline_v2_to_v3(source_yaml: str, target_yaml: str) -> int:
    """迁移v2管道YAML到v3格式"""
    import yaml as yaml_mod
    from pathlib import Path as P
    src = P(source_yaml)
    if not src.exists():
        return 0
    v2 = yaml_mod.safe_load(src.read_text(encoding="utf-8"))
    v3_stages = []
    for s in v2.get("pipeline", {}).get("stages", []):
        new_name = STAGE_NAME_MAP.get(s["name"], s["name"])
        v3_stages.append({**s, "name": new_name})
    v3 = {"pipeline": {"name": "default", "stages": v3_stages}}
    P(target_yaml).write_text(yaml_mod.dump(v3, allow_unicode=True), encoding="utf-8")
    return len(v3_stages)


def migrate_state_v2_to_v3(source_json: str, target_json: str) -> dict:
    """迁移v2项目状态到v3格式"""
    import json as json_mod
    from pathlib import Path as P
    src = P(source_json)
    if not src.exists():
        return {}
    v2 = json_mod.loads(src.read_text(encoding="utf-8"))
    v3 = {**v2}
    # 字段重命名
    for old, new in FIELD_NAME_MAP.items():
        if old in v3:
            v3[new] = v3.pop(old)
    # 阶段名映射
    if "stages" in v3:
        new_stages = {}
        for name, data in v3["stages"].items():
            new_name = STAGE_NAME_MAP.get(name, name)
            new_stages[new_name] = data
        v3["stages"] = new_stages
    # 加v3新字段
    v3.setdefault("mode", "material")
    v3.setdefault("reference_url", None)
    P(target_json).write_text(json_mod.dumps(v3, ensure_ascii=False, indent=2), encoding="utf-8")
    return v3
