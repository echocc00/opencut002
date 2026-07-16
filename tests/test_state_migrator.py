"""State 迁移测试（v0.6.1）- schema 版本化 + 大小限制 + 原子写。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.orchestrator.state_migrator import (
    migrate_state, StateMigrator, CURRENT_VERSION, _load_json_safely, _MAX_STATE_BYTES,
)


class TestMigrateState:
    def test_v1_to_v2_adds_schema_version(self):
        v1 = {"project_id": "p1"}  # 无 schema_version = v1
        data, versions = migrate_state(v1)
        assert data["schema_version"] == 2
        assert versions == [2]

    def test_v1_to_v2_adds_defaults_without_overwriting(self):
        v1 = {"project_id": "p1", "approval_mode": "full_auto"}
        data, _ = migrate_state(v1)
        assert data["approval_mode"] == "full_auto"  # 不覆盖
        assert data["mode"] == "material"  # 补默认
        assert data["schema_version"] == 2

    def test_already_v2_no_migration(self):
        v2 = {"project_id": "p1", "schema_version": 2}
        data, versions = migrate_state(v2)
        assert versions == []
        assert data["schema_version"] == 2

    def test_future_version_loaded_with_warning(self):
        future = {"project_id": "p1", "schema_version": 999}
        data, versions = migrate_state(future)
        assert versions == []
        assert data["schema_version"] == 999  # 原样


class TestLoadJsonSafely:
    def test_normal_load(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text('{"a": 1}', encoding="utf-8")
        assert _load_json_safely(p) == {"a": 1}

    def test_oversized_rejected(self, tmp_path):
        """修资源耗尽：超 _MAX_STATE_BYTES 拒绝加载。"""
        p = tmp_path / "state.json"
        p.write_text("x" * (_MAX_STATE_BYTES + 1), encoding="utf-8")
        with pytest.raises(ValueError, match="过大"):
            _load_json_safely(p)


class TestStateMigrator:
    def test_migrate_file_nonexistent_returns_none(self, tmp_path):
        m = StateMigrator()
        assert m.migrate_file(tmp_path / "nope.json") is None

    def test_migrate_file_inplace_v1(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text(json.dumps({"project_id": "p1"}), encoding="utf-8")
        m = StateMigrator()
        assert m.migrate_file_inplace(p) is True
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["schema_version"] == 2

    def test_migrate_file_inplace_already_v2_no_write(self, tmp_path):
        p = tmp_path / "state.json"
        original = json.dumps({"project_id": "p1", "schema_version": 2})
        p.write_text(original, encoding="utf-8")
        m = StateMigrator()
        assert m.migrate_file_inplace(p) is False  # 不写
        assert p.read_text(encoding="utf-8") == original  # 未改

    def test_save_migrated_atomic(self, tmp_path):
        """原子写：不留 .tmp 残留。"""
        p = tmp_path / "state.json"
        m = StateMigrator()
        m.save_migrated(p, {"project_id": "p1", "schema_version": 2})
        assert p.exists()
        assert not (tmp_path / "state.json.tmp").exists()  # 无残留

    def test_migrate_directory(self, tmp_path):
        projects = tmp_path / "projects" / "p1"
        projects.mkdir(parents=True)
        (projects / "state.json").write_text(json.dumps({"project_id": "p1"}), encoding="utf-8")
        # 已 v2 的不迁移
        p2 = tmp_path / "projects" / "p2"
        p2.mkdir(parents=True)
        (p2 / "state.json").write_text(json.dumps({"project_id": "p2", "schema_version": 2}), encoding="utf-8")
        m = StateMigrator()
        count = m.migrate_directory(tmp_path)
        assert count == 1  # 只 p1 迁移


class TestProjectStateIntegration:
    def test_load_migrates_old_state(self, tmp_path):
        """v0.6.1：ProjectState.load 自动迁移 v1 -> v2。"""
        from src.orchestrator.state import ProjectState
        projects = tmp_path / "projects" / "p1"
        projects.mkdir(parents=True)
        (projects / "state.json").write_text(
            json.dumps({"project_id": "p1", "domain": "education"}),  # v1 无 schema_version
            encoding="utf-8")
        state = ProjectState.load(tmp_path, "p1")
        assert state is not None
        assert state.schema_version == 2
        assert state.project_id == "p1"

    def test_save_load_roundtrip_preserves_schema_version(self, tmp_path):
        from src.orchestrator.state import ProjectState
        state = ProjectState(project_id="rt", domain="education")
        state.save(tmp_path)
        loaded = ProjectState.load(tmp_path, "rt")
        assert loaded is not None
        assert loaded.schema_version == 2
        # 原子写不留 tmp
        assert not (tmp_path / "projects" / "rt" / "state.json.tmp").exists()
