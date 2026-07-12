---
name: opencut-producer
description: 根据一批图片或视频素材，生产带配音、字幕、BGM 的竖版解说短视频（1080x1920）。调用 OpenCut v3 管道（20 阶段：素材分析 -> 选题 -> 文案 -> 配图 -> TTS -> 分镜 -> 渲染 -> 交付）。当用户说"用这些素材剪个视频""根据这些图片做个解说短视频""把这批视频素材剪成一条"时使用。含首次部署流程：若本机未部署，按 skill 指引解压 bundle + 跑 bootstrap 装环境 + 配 minimax/doubao API key。
---

# OpenCut 短视频生产

本 skill 指导你用 OpenCut v3 项目把素材剪成一条解说短视频。你（执行 agent）不需要
懂项目内部架构，按下面的步骤操作即可。深度参考见同目录 [reference.md](reference.md)。

## 何时使用

- 用户给了一批图片（.jpg/.png）或视频（.mp4），要剪成一条短视频
- 用户要"根据素材做个解说/配音视频"
- 产物要求：竖版 1080x1920、有配音、有字幕、有 BGM

**不适用**：用户要剪辑时间线/转场特效/纯音乐 MV（本项目是 AI 全自动解说视频）。

## 第 0 步：判断是否首次部署

先判断本机是否已部署 OpenCut v3（四个标志都要）：

```bash
ls <OPENCUT_DIR>/scripts/run_full.py \
   <OPENCUT_DIR>/.venv \
   <OPENCUT_DIR>/remotion/node_modules \
   <OPENCUT_DIR>/.env
```

- 四者都存在 -> 已部署，跳到"第 1 步：检查环境"
- 缺任意一个 -> 走"首次部署"流程

### 首次部署（从压缩包开始，仅一次）

用户给你一个 `opencut-v3-<ver>-bundle.zip`（自包含：源码 + skill + bootstrap + .env.example，
不含依赖和密钥）。按以下部署：

```bash
# 1. 解压到任意目录（Windows 也可右键解压）
unzip opencut-v3-*-bundle.zip
cd opencut-v3-*/

# 2. 一键装环境：检查 Python3.10+/Node18+/ffmpeg，建 venv，pip install，remotion npm install，初始化 .env
#    Windows:
scripts\bootstrap.bat
#    macOS/Linux:
bash scripts/bootstrap.sh
#    若某依赖缺失，bootstrap 会报 [X] 并退出，按提示装好再重跑

# 3. 配 .env：编辑 .env 填两个 key
#    MINIMAX_API_KEY=...   (LLM + TTS，必填)
#    DOUBAO_API_KEY=...    (多模态视觉，必填，否则文案对不上画面)
#    DOUBAO_MODEL 保持 doubao-seed-2-0-lite-260428

# 4. 冒烟测试（12 阶段，验证 provider key 有效，不需素材）
PYTHONUTF8=1 python scripts/run_full.py
#    期望：打印 "Provider OK" + 12 阶段全 completed
```

冒烟通过则部署完成，进入下方产视频流程。冒烟失败看排障速查。

### 定位项目根

`<OPENCUT_DIR>` = 含 `scripts/run_full.py` 的目录。后续所有命令都在此目录下执行。

## 第 1 步：检查环境

一次性确认四个依赖，缺一不可：

```bash
cd <OPENCUT_DIR>
python --version              # >= 3.10
node --version                # >= 18
ffmpeg -version               # 任意版本
ls remotion/node_modules      # 必须存在（否则 cd remotion && npm install）
ls .env                       # 必须存在且含真实 MINIMAX_API_KEY / DOUBAO_API_KEY
```

`.env` 缺 key 则让用户补（参考 `.env.example`）。**doubao key 缺失会导致文案与
画面不符**，必须配。

## 第 2 步：准备素材（.jpg）

管道只识别 `.jpg`（取前 5 张）。源是视频时先抽帧：

```bash
# 用户给了视频：每 5 秒抽一帧到目标目录
PROJECT_ID=<给本次视频起个 id，如 fuxue_20260712>
mkdir -p data/projects/$PROJECT_ID/materials
ffmpeg -i <源视频.mp4> -vf fps=1/5 data/projects/$PROJECT_ID/materials/frame_%02d.jpg
```

抽完后**人工或让用户挑 5-10 张代表不同场景的帧**（避免连续相似帧），多余的删掉。
管道只取前 5 张，所以保证前 5 张是不同场景。

源已是图片则直接拷进去：
```bash
mkdir -p data/projects/$PROJECT_ID/materials
cp <用户图片>.jpg data/projects/$PROJECT_ID/materials/
```

## 第 3 步：选领域

`--domain` 四选一，按素材内容：

| domain | 适用 |
|--------|------|
| `education` | 教培、学习、课堂（默认） |
| `travel` | 旅行、风景、目的地 |
| `knowledge_paid` | 知识付费、干货、专家 |
| `custom` | 都不沾边时（模板，配置较中性） |

不确定就 `education` 或 `custom`。

## 第 4 步：跑管道

```bash
cd <OPENCUT_DIR>
.venv/Scripts/activate          # Windows；macOS/Linux: source .venv/bin/activate
PYTHONUTF8=1 python scripts/run_full.py --full \
  --materials-dir data/projects/$PROJECT_ID/materials \
  --project-id $PROJECT_ID \
  --domain <domain>
```

耗时约 3-8 分钟（TTS + 渲染是大头）。过程中会打印每个阶段状态。

**断点续跑**：若中途失败，直接重跑同一命令，已完成的阶段跳过，失败的自动重试。
要完全重跑则删 `data/projects/$PROJECT_ID/state.json`。

## 第 5 步：验收产物

```bash
# 1. 产物存在
ls -lh data/projects/$PROJECT_ID/output/final.mp4

# 2. 时长合理（20-90 秒为正常区间）
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 \
  data/projects/$PROJECT_ID/output/final.mp4

# 3. 有音轨
ffprobe -v error -select_streams a -show_entries stream=codec_type \
  -of default=noprint_wrappers=1:nokey=1 data/projects/$PROJECT_ID/output/final.mp4
# 应输出 audio

# 4. 各阶段状态（看 state.json 里有没有 error / pending）
python -c "import json; s=json.load(open('data/projects/$PROJECT_ID/state.json',encoding='utf-8')); [print(f'{n}: {st[\"status\"]}') for n,st in s['stages'].items()]"
# 期望全部 completed
```

验收通过则把 `final.mp4` 路径告诉用户，完成。

## 排障速查

| 现象 | 原因 / 解法 |
|------|-------------|
| `UnicodeEncodeError` | 命令前加 `PYTHONUTF8=1` |
| 渲染阶段 npx 找不到 | `cd remotion && npm install` |
| 渲染报 file:// 错误 | 不应出现（render_agent 自动 stage 到 public/）；若出现，看 `render_agent.py` |
| 视频没声音 | TTS 失败。看 state.json 的 `tts.error`，确认 `MINIMAX_API_KEY` 有效 |
| 文案描述与画面不符 | doubao 未生效。确认 `.env` 的 `DOUBAO_MODEL=doubao-seed-2-0-lite-260428`（不是显示名） |
| 最后一句没画面/字幕 | copywriting 段落被拆碎；检查 state.json 的 `copywriting.paragraphs` 是完整句子 |
| 某阶段一直 error | 看 `data/projects/$PROJECT_ID/decisions.jsonl` 决策日志 + state.json 的 error 字段 |

更多坑与管道详解见 [reference.md](reference.md)。

## 给执行 agent 的守则

- **不要改项目代码**来"修"问题，除非用户明确要求。优先用排障速查。
- **不要 commit** `.env` 或任何含 key 的文件。
- **素材前 5 张决定视频质量**：帮用户挑差异化场景的帧。
- **project-id 唯一**：每次产视频用新 id，避免覆盖旧项目；可复用 id 来续跑/重跑。
- 跑完向用户报告：产物路径 + 时长 + 各阶段是否全绿。
