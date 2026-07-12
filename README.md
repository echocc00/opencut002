# OpenCut v3

AI 驱动的多领域短视频生产平台。输入素材图片 + 领域配置，自动产出带配音、字幕、
BGM 的竖版短视频（1080x1920）。

## 快速开始（5 步出片）

### 1. 装环境

需要：Python 3.10+（推荐 3.12）、Node.js 18+、ffmpeg、git。

一键装（推荐）：
```bash
git clone https://github.com/echocc00/opencut002.git opencut-v3 && cd opencut-v3
scripts\bootstrap.bat          # Windows
# bash scripts/bootstrap.sh    # macOS/Linux
# bootstrap 会：建 venv + pip install + remotion npm install + 从 .env.example 初始化 .env
```

或手动：
```bash
git clone https://github.com/echocc00/opencut002.git opencut-v3 && cd opencut-v3
python -m venv .venv
.venv/Scripts/activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"
cd remotion && npm install && cd ..
cp .env.example .env
```

### 2. 配 API Key

```bash
cp .env.example .env
```

编辑 `.env`，至少填：
- `MINIMAX_API_KEY` -- LLM + TTS + 多模态视觉（必填）
- `DOUBAO_API_KEY` -- 多模态视觉备用 fallback（可选，minimax M3 已支持多模态）

### 3. 准备素材

管道只识别 `.jpg` 图片（取前 5 张）。源是视频时先抽帧：

```bash
# 每 5 秒抽一帧
ffmpeg -i 源视频.mp4 -vf fps=1/5 frame_%02d.jpg
```

挑 5-10 张代表不同场景的帧，放进一个目录，例如 `data/projects/myvideo/materials/`。

### 4. 跑管道

```bash
python scripts/run_full.py --full \
  --materials-dir data/projects/myvideo/materials \
  --project-id myvideo \
  --domain education
```

`--domain` 可选：`education` / `travel` / `knowledge_paid` / `custom`。

### 5. 取产物

```
data/projects/myvideo/output/final.mp4
```

## 命令参考

```bash
# 冒烟测试（12 阶段，不需 ffmpeg/Node）
python scripts/run_full.py

# 完整管道（20 阶段，含 TTS + 渲染）
python scripts/run_full.py --full --materials-dir <dir> --project-id <id> --domain <domain>

# 断点续跑：直接重跑同一命令，已完成的阶段跳过，失败的自动重试
# 完全重跑：删 data/projects/<id>/state.json
```

## 管道阶段（20）

```
material_analysis -> web_research -> topic -> highlight_selection -> copywriting
-> image_matching -> voice_selection -> tts -> storyboard
-> opening_review -> slideshow_check        # 质量关卡
-> bgm -> rhythm -> title -> cover -> fine_cut
-> pre_render_check                          # 质量关卡
-> render -> post_render_check -> deliver     # 质量关卡 + 交付
```

数据流契约见 [docs/data-flow-contract.md](docs/data-flow-contract.md)。

## 领域配置

| 领域 | 说明 |
|------|------|
| `education` | 教培（辅学有道等） |
| `travel` | 旅行 |
| `knowledge_paid` | 知识付费 |
| `custom` | 模板，用于新建领域 |

新增领域：复制 `domains/custom`（或 `domains/travel`），改 `style.yaml` /
`highlights.json` / `voices.json` / `research.json` / `opening_templates.yaml`，
换 `bgm/*.mp3`。详见 [domains/custom/README.md](domains/custom/README.md)。

## 测试

```bash
PYTHONUTF8=1 pytest                                  # 全量（覆盖率门槛 80%）
PYTHONUTF8=1 pytest tests/test_m10_remotion.py -v    # 渲染管道
```

## 常见问题

**Q: 跑到渲染阶段报错 / 提示 npx 找不到**
A: 确认 `remotion/node_modules` 已安装（`cd remotion && npm install`），且 `npx` 在 PATH。

**Q: Windows 下中文报 `UnicodeEncodeError`**
A: 设环境变量 `PYTHONUTF8=1` 再跑。`run_full.py` 已内置 UTF-8 重配，但部分子进程可能仍需。

**Q: 素材分析把画面描述错了（如教室说成雪山）**
A: 素材分析优先用 minimax M3 多模态（检查 `MINIMAX_API_KEY`），doubao 次之
   （`DOUBAO_API_KEY` + 模型 `doubao-seed-2-0-lite-260428`）。纯文本 provider 看不见图会幻觉，
   不要回退到纯文本。

**Q: 视频没声音**
A: TTS 用 minimax 同步 `t2a_v2`（响应 `data.audio` 是 hex MP3，Bearer 鉴权，无轮询）。
   确认 `MINIMAX_API_KEY` 有效，看 `data/projects/<id>/state.json` 的 `tts` 阶段 `error` 字段。

**Q: 字幕和画面/配音对不上**
A: 当前是段落级对齐（1 段文案 = 1 段 TTS = 1 个分镜段）。若文案被拆碎，检查
   `copywriting` 阶段输出的 `paragraphs` 是否完整句子。

**Q: 想换领域音色/BGM**
A: 改 `domains/<domain>/voices.json` 和 `bgm/*.mp3`。

**Q: 想用自己的音色（音色复刻）**
A: `python scripts/clone_voice.py --audio <参考音频> --voice-id <自定义ID>` 克隆，
   再配到 `domains/<domain>/voices.json` 的 `minimax_voice_id`。详见 [CLAUDE.md](CLAUDE.md)。

## 文档

- [CLAUDE.md](CLAUDE.md) -- AI agent 操作手册
- [docs/data-flow-contract.md](docs/data-flow-contract.md) -- 数据流与跨语言契约
- [domains/custom/README.md](domains/custom/README.md) -- 新建领域指南
- [.claude/skills/opencut-producer/SKILL.md](.claude/skills/opencut-producer/SKILL.md) -- Claude Code skill

## 许可证

本项目采用 [GPL-3.0](LICENSE) 协议。任何人可自由使用、修改、分发，但衍生作品必须
同样以 GPL-3.0 开源，并保留版权与许可声明。
