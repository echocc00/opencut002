"""State schema 版本化 + 迁移（v0.6.1，port 自 v0.5.4 audit + 修复）。

ProjectState 演进：
- v1（legacy）：无 schema_version 字段
- v2（当前）：加 schema_version + 更好默认

StateMigrator 负责把旧 state.json 迁到当前 schema。每个迁移函数注册在 MIGRATIONS
里，按源版本号 key。迁移用 setdefault（不覆盖用户数据）。

修复（评审 MEDIUM）：
- json.load 前校验文件大小（防资源耗尽 / 解压炸弹）
- setdefault 改 approval_mode 时 log 警告（静默安全姿态变更）
- save_migrated 原子写（tmp+rename）
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


CURRENT_VERSION = 2

# state.json 最大允许大小（10MB），超了拒绝加载（防资源耗尽）
_MAX_STATE_BYTES = 10 * 1024 * 1024


def _v1_to_v2(data: dict) -> dict:
    """v1（无 schema_version）-> v2。

    v1 缺：schema_version、approval_mode、mode、last_provider、decision_log_path 等。
    """
    if "schema_version" not in data:
        data["schema_version"] = 2
    # approval_mode 静默改变工作流姿态（manual vs full_auto），记日志提醒运维
    if "approval_mode" not in data:
        log.warning("state 迁移：补 approval_mode='manual'（旧项目无此字段，默认手动审批）")
        data["approval_mode"] = "manual"
    data.setdefault("mode", "material")
    data.setdefault("last_provider", "")
    data.setdefault("decision_log_path", None)
    data.setdefault("user_notes", {})
    data.setdefault("materials", [])
    data.setdefault("quality_reports", [])
    data.setdefault("cost_total", 0.0)
    return data


MIGRATIONS: dict[int, Callable[[dict], dict]] = {
    1: _v1_to_v2,
    # 未来：2: _v2_to_v3, ...
}


def migrate_state(data: dict) -> tuple[dict, list[int]]:
    """把 data 迁到 CURRENT_VERSION。返回 (迁移后 data, 经过的版本列表)。"""
    current = data.get("schema_version", 1)  # 缺失 = v1
    applied: list[int] = []

    if current > CURRENT_VERSION:
        log.warning(f"state schema_version {current} 比支持的 {CURRENT_VERSION} 新，原样加载（可能有问题）")
        data.setdefault("schema_version", current)
        return data, []

    while current < CURRENT_VERSION:
        if current not in MIGRATIONS:
            raise RuntimeError(f"无法迁移：无 v{current} -> v{current + 1} 处理器")
        log.info(f"应用迁移 v{current} -> v{current + 1}")
        data = MIGRATIONS[current](data)
        current = data.get("schema_version", current + 1)
        applied.append(current)

    return data, applied


def _load_json_safely(path: Path) -> dict:
    """读 state.json，带大小校验（防资源耗尽）。"""
    size = path.stat().st_size
    if size > _MAX_STATE_BYTES:
        raise ValueError(f"state.json 过大（{size} bytes > {_MAX_STATE_BYTES}），拒绝加载")
    return json.loads(path.read_text(encoding="utf-8"))


class StateMigrator:
    """state.json 迁移辅助类。"""

    def __init__(self, current_version: int = CURRENT_VERSION):
        self.current_version = current_version

    def migrate_file(self, path: Path) -> Optional[dict]:
        """加载 + 迁移，返回迁移后 dict（不改原文件）。文件不存在返 None。"""
        if not path.exists():
            return None
        data = _load_json_safely(path)
        data, versions = migrate_state(data)
        log.info(f"迁移 {path}，经过版本: {versions or '(已是当前版本)'}")
        return data

    def save_migrated(self, path: Path, data: dict) -> None:
        """原子写迁移后数据（tmp + rename）。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def migrate_file_inplace(self, path: Path) -> bool:
        """迁移并写回。已是当前版本则不写，返 False。"""
        if not path.exists():
            return False
        original = _load_json_safely(path)
        if original.get("schema_version", 1) >= self.current_version:
            return False
        data = self.migrate_file(path)
        if data is None:
            return False
        self.save_migrated(path, data)
        return True

    def migrate_directory(self, data_dir: Path) -> int:
        """迁移 data/projects/*/state.json，返迁移文件数。"""
        projects_dir = data_dir / "projects"
        if not projects_dir.exists():
            return 0
        count = 0
        for state_file in projects_dir.rglob("state.json"):
            if self.migrate_file_inplace(state_file):
                count += 1
        return count
