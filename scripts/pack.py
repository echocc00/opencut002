"""打包 OpenCut v3 为可分发 zip。

排除：依赖（.venv / node_modules）、运行时（data / remotion/public）、
密钥（.env / minimax-key.txt）、缓存（__pycache__ / .pytest_cache / .coverage）。
保留：源码、领域配置、skill、bootstrap、.env.example、文档。

用法：python scripts/pack.py
产出：opencut-v3-<version>-bundle.zip
"""
from __future__ import annotations

import fnmatch
import sys
import zipfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

ROOT = Path(__file__).resolve().parent.parent
import os
os.chdir(ROOT)

VERSION = "0.5.0"
if tomllib:
    try:
        with open("pyproject.toml", "rb") as f:
            VERSION = tomllib.load(f)["project"]["version"]
    except Exception:
        pass

OUT = ROOT / f"opencut-v3-{VERSION}-bundle.zip"

EXCLUDE_DIRS = {
    ".venv", ".git", "__pycache__", ".pytest_cache", "opencut_v3.egg-info",
    "remotion/node_modules", "remotion/out", "remotion/.cache", "remotion/build",
    "data", "remotion/public", "out",
}
EXCLUDE_FILES = {
    ".env", "minimax-key.txt", ".coverage", "final_result.txt",
    "full_result.txt", "pipeline_result.txt", "remaining_result.txt",
    "run_output.txt", ".DS_Store", "Thumbs.db",
}
EXCLUDE_PATTERNS = ["*.pyc", "*.pyo", "*.log", "remotion/input*.json"]
KEEP_FILES = {"data/.gitkeep", "remotion/public/.gitkeep"}


def excluded(rel: str) -> bool:
    if rel in KEEP_FILES:
        return False
    for d in EXCLUDE_DIRS:
        if rel == d or rel.startswith(d + "/"):
            return True
    name = rel.rsplit("/", 1)[-1]
    if name in EXCLUDE_FILES or rel in EXCLUDE_FILES:
        return True
    for pat in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(name, pat):
            return True
    return False


def main() -> int:
    for keep in KEEP_FILES:
        p = ROOT / keep
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch(exist_ok=True)

    if OUT.exists():
        OUT.unlink()

    count = 0
    total = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        # 保留的占位文件（其父目录被 EXCLUDE_DIRS 剪掉，单独写入）
        for keep in KEEP_FILES:
            p = ROOT / keep
            zf.write(p, arcname=f"opencut-v3-{VERSION}/{keep}")
            count += 1
            total += p.stat().st_size
        for dirpath, dirnames, filenames in os.walk(ROOT):
            dirnames[:] = sorted(d for d in dirnames
                                 if f"{Path(dirpath).relative_to(ROOT).as_posix()}/{d}".lstrip("/")
                                 not in EXCLUDE_DIRS
                                 and d not in EXCLUDE_DIRS)
            for name in sorted(filenames):
                path = Path(dirpath) / name
                rel = path.relative_to(ROOT).as_posix()
                if excluded(rel):
                    continue
                zf.write(path, arcname=f"opencut-v3-{VERSION}/{rel}")
                count += 1
                total += path.stat().st_size

    size_mb = OUT.stat().st_size / 1024 / 1024
    print(f"产出: {OUT.name}")
    print(f"文件数: {count}")
    print(f"未压缩: {total / 1024 / 1024:.1f} MB")
    print(f"压缩后: {size_mb:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
