"""ToolRuntime 分类测试（v0.6.2）。"""
from __future__ import annotations

import pytest

from src.providers.provider_registry import (
    Provider, ToolRuntime, register_provider, clear_registry,
    list_providers, list_providers_by_runtime,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


class TestToolRuntimeEnum:
    def test_values(self):
        assert ToolRuntime.LOCAL.value == "local"
        assert ToolRuntime.LOCAL_GPU.value == "local_gpu"
        assert ToolRuntime.API.value == "api"
        assert ToolRuntime.HYBRID.value == "hybrid"

    def test_is_str_enum(self):
        assert isinstance(ToolRuntime.API, str)


class TestProviderRuntime:
    def test_default_runtime_is_api(self):
        p = Provider("x")
        assert p.runtime == ToolRuntime.API

    def test_explicit_runtime(self):
        p = Provider("gpu_tool", runtime=ToolRuntime.LOCAL_GPU)
        assert p.runtime == ToolRuntime.LOCAL_GPU

    def test_backward_compat_two_args(self):
        """现有调用只传 name+complete_fn，runtime 用默认。"""
        p = Provider("x", complete_fn=None)
        assert p.runtime == ToolRuntime.API
        assert p.name == "x"


class TestListByRuntime:
    def test_filters_by_runtime(self):
        register_provider("api_a", Provider("api_a", runtime=ToolRuntime.API))
        register_provider("api_b", Provider("api_b", runtime=ToolRuntime.API))
        register_provider("gpu_c", Provider("gpu_c", runtime=ToolRuntime.LOCAL_GPU))

        api = list_providers_by_runtime(ToolRuntime.API)
        assert sorted(api) == ["api_a", "api_b"]
        assert list_providers_by_runtime(ToolRuntime.LOCAL_GPU) == ["gpu_c"]
        assert list_providers_by_runtime(ToolRuntime.LOCAL) == []

    def test_list_providers_still_returns_all(self):
        register_provider("a", Provider("a"))
        register_provider("b", Provider("b", runtime=ToolRuntime.LOCAL_GPU))
        assert sorted(list_providers()) == ["a", "b"]


class TestToolRuntimeConstants:
    """工具模块声明 RUNTIME 常量（为未来 tool registry 铺路）。"""

    def test_forced_align_runtime(self):
        from src.tools.forced_align import RUNTIME
        assert RUNTIME == ToolRuntime.LOCAL_GPU

    def test_face_masker_runtime(self):
        from src.tools.face_masker import RUNTIME
        assert RUNTIME == ToolRuntime.LOCAL
