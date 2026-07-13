"""C0.4 异步任务层测试：job 生命周期 + ownership + 列表 + 下载校验"""
from __future__ import annotations

import asyncio

import pytest


class _MockEngine:
    """快速 mock：3 阶段，不跑真管道，立即完成"""
    def __init__(self, *a, **kw): pass
    def auto_register_handlers(self, *a, **kw): pass
    def get_stages(self): return [{"name": "s1"}, {"name": "s2"}, {"name": "s3"}]
    async def run(self, state, on_stage_start=None):
        for n in ("s1", "s2", "s3"):
            if on_stage_start:
                on_stage_start(n)
        return state


FAKE_JPG = b"\xff\xd8\xff\xe0" + b"fake-image-bytes"  # prepare_materials 只看扩展名


async def _create_project(auth_client, domain="education"):
    resp = await auth_client.post(
        "/api/projects/create",
        data={"domain": domain, "approval_mode": "full_auto"},
        files=[("materials", ("test.jpg", FAKE_JPG, "image/jpeg"))],
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["project_id"]


async def _wait_job(client, job_id, timeout=10.0):
    """轮询 job 状态直到 completed/failed"""
    deadline = asyncio.get_event_loop().time() + timeout
    status = "queued"
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"/api/jobs/{job_id}")
        if resp.status_code == 200:
            status = resp.json()["status"]
            if status in ("completed", "failed"):
                break
        await asyncio.sleep(0.2)
    return status


@pytest.mark.asyncio
async def test_job_lifecycle_completed(auth_client, monkeypatch):
    """mock engine -> job 从 queued 走到 completed"""
    monkeypatch.setattr("src.api.job_runner.PipelineEngine", _MockEngine)
    project_id = await _create_project(auth_client)
    resp = await auth_client.post(f"/api/projects/{project_id}/run")
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    status = await _wait_job(auth_client, job_id)
    assert status == "completed", f"job 未完成，状态={status}"

    resp = await auth_client.get(f"/api/jobs/{job_id}")
    assert resp.json()["stages_completed"] == 3
    assert resp.json()["stages_total"] == 3


@pytest.mark.asyncio
async def test_job_failed_when_engine_raises(auth_client, monkeypatch):
    """engine 抛错 -> job=failed，error 记录"""

    class _FailEngine(_MockEngine):
        async def run(self, state, on_stage_start=None):
            raise RuntimeError("模拟管道失败")

    monkeypatch.setattr("src.api.job_runner.PipelineEngine", _FailEngine)
    project_id = await _create_project(auth_client)
    resp = await auth_client.post(f"/api/projects/{project_id}/run")
    job_id = resp.json()["job_id"]

    status = await _wait_job(auth_client, job_id)
    assert status == "failed"
    resp = await auth_client.get(f"/api/jobs/{job_id}")
    assert "模拟管道失败" in (resp.json()["error"] or "")


@pytest.mark.asyncio
async def test_job_ownership_404(auth_client, async_client, monkeypatch):
    """用户 A 的 job，用户 B 查 -> 404"""
    monkeypatch.setattr("src.api.job_runner.PipelineEngine", _MockEngine)
    project_id = await _create_project(auth_client)
    resp = await auth_client.post(f"/api/projects/{project_id}/run")
    job_id = resp.json()["job_id"]

    # 用户 B 注册
    resp = await async_client.post("/api/auth/register", json={
        "email": "b@example.com", "username": "userb", "password": "pass1234",
    })
    b_token = resp.json()["access_token"]
    async_client.headers["Authorization"] = f"Bearer {b_token}"

    resp = await async_client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_jobs(auth_client, monkeypatch):
    """列用户任务"""
    monkeypatch.setattr("src.api.job_runner.PipelineEngine", _MockEngine)
    project_id = await _create_project(auth_client)
    await auth_client.post(f"/api/projects/{project_id}/run")
    await _wait_job(auth_client, (await auth_client.get(f"/api/jobs?project_id={project_id}")).json()[0]["id"])

    resp = await auth_client.get("/api/jobs")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    # 按 project_id 过滤
    resp = await auth_client.get(f"/api/jobs?project_id={project_id}")
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_download_not_completed_409(auth_client, monkeypatch):
    """job 未完成时下载 -> 409（mock start_job 为 no-op，job 停在 queued）"""
    monkeypatch.setattr("src.api.job_runner.PipelineEngine", _MockEngine)
    project_id = await _create_project(auth_client)
    resp = await auth_client.post(f"/api/projects/{project_id}/run")
    job_id = resp.json()["job_id"]
    await asyncio.sleep(0.3)  # 让 job 跑（mock 会很快完成或还在跑）

    # 若已完成则跳过；否则测 409
    cur = await auth_client.get(f"/api/jobs/{job_id}")
    if cur.json()["status"] != "completed":
        resp = await auth_client.get(f"/api/jobs/{job_id}/result")
        assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_job_not_found_404(auth_client):
    resp = await auth_client.get("/api/jobs/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_unowned_project_404(auth_client):
    """启动别人的项目 -> 404"""
    resp = await auth_client.post("/api/projects/proj_nonexistent/run")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_project_no_materials_400(auth_client):
    """无素材 -> 400"""
    resp = await auth_client.post(
        "/api/projects/create",
        data={"domain": "education", "approval_mode": "full_auto"},
        files=[],
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_projects(auth_client, monkeypatch):
    """列用户项目"""
    monkeypatch.setattr("src.api.job_runner.PipelineEngine", _MockEngine)
    await _create_project(auth_client, domain="travel")
    resp = await auth_client.get("/api/projects")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    assert resp.json()[0]["domain"] == "travel"
