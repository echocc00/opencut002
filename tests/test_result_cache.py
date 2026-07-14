"""result_cache 单元测试"""
import os
import json
from pathlib import Path
import pytest
from src.tools import result_cache


@pytest.fixture
def cache_enabled(monkeypatch, tmp_path, chdir_tmp):
    monkeypatch.setenv("OPENCUT_CACHE", "1")
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def chdir_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_is_enabled_default_off():
    # 默认未设环境变量 -> 关
    assert result_cache.is_enabled() is False or os.environ.get("OPENCUT_CACHE", "").strip().lower() in ("1", "true", "yes", "on")


def test_is_enabled_on(monkeypatch):
    monkeypatch.setenv("OPENCUT_CACHE", "1")
    assert result_cache.is_enabled() is True


def test_is_enabled_off(monkeypatch):
    monkeypatch.setenv("OPENCUT_CACHE", "0")
    assert result_cache.is_enabled() is False


def test_make_key_stable():
    a = result_cache.make_key("hello", "world", 1.2)
    b = result_cache.make_key("hello", "world", 1.2)
    assert a == b
    assert len(a) == 16


def test_make_key_differs_on_input():
    a = result_cache.make_key("hello", "world")
    b = result_cache.make_key("hello", "word")
    assert a != b


def test_make_key_separator_prevents_collision():
    # "ab"+"c" != "a"+"bc"
    a = result_cache.make_key("ab", "c")
    b = result_cache.make_key("a", "bc")
    assert a != b


def test_set_get_bytes_roundtrip(cache_enabled):
    key = result_cache.make_key("text1", "voice1")
    result_cache.set_bytes(key, "tts", "mp3", b"\x49\x44\x33audio")
    got = result_cache.get_bytes(key, "tts", "mp3")
    assert got == b"\x49\x44\x33audio"


def test_get_bytes_miss_returns_none(cache_enabled):
    got = result_cache.get_bytes("nonexistent_key", "tts", "mp3")
    assert got is None


def test_set_get_json_roundtrip(cache_enabled):
    key = result_cache.make_key("prompt1")
    obj = {"images": [{"file": "a.jpg", "scene": "教室"}], "destination": "学校"}
    result_cache.set_json(key, "material_analysis", obj)
    got = result_cache.get_json(key, "material_analysis")
    assert got == obj


def test_disabled_no_op(monkeypatch, chdir_tmp):
    monkeypatch.setenv("OPENCUT_CACHE", "0")
    key = result_cache.make_key("x")
    result_cache.set_bytes(key, "tts", "mp3", b"data")
    result_cache.set_json(key, "llm", {"a": 1})
    assert result_cache.get_bytes(key, "tts", "mp3") is None
    assert result_cache.get_json(key, "llm") is None


def test_make_key_with_file_path(cache_enabled, tmp_path):
    # 相同路径 + 相同内容 -> 相同 key
    f1 = tmp_path / "img1.jpg"
    f1.write_bytes(b"image-data")
    k1 = result_cache.make_key("prompt", f1)
    k2 = result_cache.make_key("prompt", f1)
    assert k1 == k2

    # 内容变了 -> key 变
    f1.write_bytes(b"changed")
    k3 = result_cache.make_key("prompt", f1)
    assert k3 != k1
