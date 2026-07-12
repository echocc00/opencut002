#!/usr/bin/env bash
# OpenCut v3 bootstrap - macOS/Linux 一键装环境
set -e
cd "$(dirname "$0")/.."

echo "============================================"
echo "  OpenCut v3 bootstrap"
echo "============================================"

# 1. Python
if ! command -v python3 >/dev/null 2>&1; then
  echo "[X] Python3 未安装。请装 Python 3.10+"; exit 1
fi
PYV=$(python3 --version 2>&1 | awk '{print $2}')
echo "[OK] Python $PYV"

# 2. Node
if ! command -v node >/dev/null 2>&1; then
  echo "[X] Node.js 未安装。请装 Node 18+"; exit 1
fi
echo "[OK] Node $(node --version)"

# 3. ffmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "[X] ffmpeg 未安装。请装 ffmpeg"; exit 1
fi
echo "[OK] ffmpeg"

# 4. venv + pip
if [ ! -d .venv ]; then
  echo "--- 创建 Python venv ---"
  python3 -m venv .venv
fi
source .venv/bin/activate
echo "--- pip install ---"
python -m pip install --upgrade pip >/dev/null
pip install -e ".[dev]"
echo "[OK] Python 依赖"

# 5. Remotion
if [ ! -d remotion/node_modules ]; then
  echo "--- npm install remotion ---"
  (cd remotion && npm install)
else
  echo "[OK] remotion/node_modules 已存在，跳过"
fi

# 6. .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "============================================"
  echo "  环境就绪。下一步："
  echo "  1. 编辑 .env 填 MINIMAX_API_KEY 和 DOUBAO_API_KEY"
  echo "  2. 准备素材 .jpg 到某目录"
  echo "  3. python scripts/run_full.py --full --materials-dir <dir> --project-id <id> --domain education"
  echo "============================================"
else
  echo "[OK] .env 已存在"
fi
