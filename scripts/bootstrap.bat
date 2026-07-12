@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
echo ============================================
echo   OpenCut v3 bootstrap
echo ============================================

REM 1. Python
python --version >nul 2>&1
if errorlevel 1 (
  echo [X] Python 未安装。请装 Python 3.10+: https://www.python.org/
  exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYV=%%v
echo [OK] Python %PYV%

REM 2. Node
node --version >nul 2>&1
if errorlevel 1 (
  echo [X] Node.js 未安装。请装 Node 18+: https://nodejs.org/
  exit /b 1
)
for /f "tokens=1 delims= " %%v in ('node --version 2^>^&1') do set NODEV=%%v
echo [OK] Node %NODEV%

REM 3. ffmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
  echo [X] ffmpeg 未安装。请装 ffmpeg 并加入 PATH。
  exit /b 1
)
echo [OK] ffmpeg

REM 4. venv + pip
if not exist .venv (
  echo --- 创建 Python venv ---
  python -m venv .venv
)
call .venv\Scripts\activate
echo --- pip install ---
python -m pip install --upgrade pip >nul
pip install -e ".[dev]"
if errorlevel 1 ( echo [X] pip install 失败 & exit /b 1 )
echo [OK] Python 依赖

REM 5. Remotion
if not exist remotion\node_modules (
  echo --- npm install remotion ---
  pushd remotion
  call npm install
  if errorlevel 1 ( echo [X] npm install 失败 & popd & exit /b 1 )
  popd
) else (
  echo [OK] remotion/node_modules 已存在，跳过
)

REM 6. .env
if not exist .env (
  copy .env.example .env >nul
  echo.
  echo ============================================
  echo   环境就绪。下一步：
  echo   1. 编辑 .env 填 MINIMAX_API_KEY 和 DOUBAO_API_KEY
  echo   2. 准备素材 .jpg 到某目录
  echo   3. python scripts\run_full.py --full --materials-dir ^<dir^> --project-id ^<id^> --domain education
  echo ============================================
) else (
  echo [OK] .env 已存在
)

endlocal
