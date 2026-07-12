# CLAUDE.md

本文件是给 AI agent（Claude Code 等）的项目操作手册。打开本项目时自动加载。
人 类阅读入口见 [README.md](README.md)。

## 项目是什么

OpenCut v3 —— AI 驱动的多领域短视频生产平台。输入一批素材图片 + 领域配置，
经 20 阶段管道（素材分析 → 选题 → 文案 → 配图 → TTS → 分镜 → BGM → 渲染 → 交付）
产出一条带配音、字幕、BGM 的竖版短视频（1080x1920）。

## 一条命令跑通

```bash
# 1. 激活 Python venv（Python 3.10+，推荐 3.12）
.venv/Scripts/activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 2. 跑完整管道（含 TTS + 渲染）
python scripts/run_full.py --full \
  --materials-dir data/projects/<id>/materials \
  --project-id <id> \
  --domain education
```

产物：`data/projects/<id>/output/final.mp4`

冒烟测试（不需 ffmpeg/Node，12 阶段）：`python scripts/run_full.py`（默认参数）

## 环境要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | >=3.10（推荐 3.12） | 管道主体 |
| Node.js | >=18 | Remotion 渲染 |
| npm/npx | 随 Node | Remotion CLI |
| ffmpeg + ffprobe | 任意 | 抽帧 / 音频拼接 / 时长探测 |

首次部署（一键）：
```bash
scripts\bootstrap.bat        # Windows（检查依赖 + 建 venv + pip install + npm install + 初始化 .env）
bash scripts/bootstrap.sh    # macOS/Linux
# 然后编辑 .env 填真实 key
```

或手动：
```bash
python -m venv .venv && .venv/Scripts/activate
pip install -e ".[dev]"
cd remotion && npm install && cd ..
cp .env.example .env   # 然后填真实 key
```

分发打包：`python scripts/pack.py` 产出 `opencut-v3-<ver>-bundle.zip`（约 4 MB，
自包含源码+skill+bootstrap，可拷到其他机器解压即用，详见
[.claude/skills/opencut-producer/INSTALL.md](.claude/skills/opencut-producer/INSTALL.md)）。

## .env 必填项

| 变量 | 说明 |
|------|------|
| `MINIMAX_API_KEY` | **必填**。同时用于 LLM（默认 provider）和 TTS |
| `MINIMAX_API_BASE` | `https://api.minimaxi.com/anthropic` |
| `MINIMAX_MODEL` | `MiniMax M3` |
| `DOUBAO_API_KEY` | 可选 fallback。minimax M3 已支持多模态视觉（优先用），doubao 作备用 |
| `DOUBAO_API_BASE` | `https://ark.cn-beijing.volces.com/api/v3` |
| `DOUBAO_MODEL` | `doubao-seed-2-0-lite-260428`（多模态，注意是模型 ID 不是显示名） |
| `PEXELS_API_KEY` | 可选，补充素材 |

占位符 key（`your_xxx` / `sk-xxx`）会被自动跳过。至少一个真实 key 才能运行。

## 架构（六层）

```
api/        HTTP 入口（FastAPI）
orchestrator/  管道引擎 + 状态 + 审批 + 质量关卡
agents/     20 个阶段 Agent（每个阶段一个）
tools/      领域无关工具（TTS / Remotion 渲染 / 图像匹配 / 转写）
providers/  多 LLM provider 适配（minimax / doubao / deepseek / qwen）
config.py   领域配置加载（domains/<domain>/）
data/       项目状态与产物（data/projects/<id>/）
```

跨语言数据契约（Python → Remotion）见 [docs/data-flow-contract.md](docs/data-flow-contract.md)。
**改任何渲染数据字段前必读此文档**：Python 侧 snake_case，Remotion 侧 camelCase，
转换在 `RemotionRenderer.build_render_data()`。

## 领域

内置 4 个：`education` / `travel` / `knowledge_paid` / `custom`（模板）。
每个领域目录含：`style.yaml` / `highlights.json` / `voices.json` / `research.json` /
`opening_templates.yaml` / `bgm/*.mp3` / `skills/*.md`（各阶段 prompt 指导）。

新增领域：复制 `domains/custom` 或 `domains/travel`，改配置 + 换 BGM。详见
[domains/custom/README.md](domains/custom/README.md)。

## 已知坑（务必遵守）

1. **Windows 编码**：控制台默认 GBK，中文/emoji 会 `UnicodeEncodeError`。
   `run_full.py` 已强制 UTF-8；跑测试前设 `PYTHONUTF8=1`。

2. **Remotion 禁用 file://**：无头 Chrome 不允许 `file://` 加载本地资源。
   `render_agent` 自动把素材拷到 `remotion/public/<project_id>/` 解决。
   不要在渲染数据里塞绝对路径，用相对项目根的路径。

3. **TTS 用 minimax async**：`t2a_async_v2`（非 edge-tts，非同步 t2a_v2）。
   逐段合成 → ffprobe 探时长 → ffmpeg concat 拼接。TTS 是时间源，不做转写对齐。

4. **素材分析必须用多模态视觉**：文本 LLM 看不见图，会幻觉（把教室说成雪山）。
   `material_analysis_agent` 优先 minimax M3 多模态，doubao 次之，不要回退到纯文本 provider。

5. **素材必须是 .jpg**：`run_full.py` 只 glob `*.jpg`（取前 5 张）。
   源是视频时先 ffmpeg 抽帧：`ffmpeg -i src.mp4 -vf fps=1/5 frame_%02d.jpg`
  （每 5 秒一帧，挑 5-10 张代表不同场景的）。

6. **字幕是整段淡入**：不逐词高亮。句子-画面对齐由段落级 TTS 时长保证
   （1 段文案 = 1 段 TTS = 1 个分镜段）。改字幕组件见
   `remotion/src/components/WordByWordSubtitle.tsx`。

7. **doubao 模型 ID**：用 `doubao-seed-2-0-lite-260428`，不是显示名
   `Doubao-Seed-2.0-lite`（会 404）。

## Agent 操作守则

- **改代码前**：先读 [docs/data-flow-contract.md](docs/data-flow-contract.md) 确认契约；
  改 Agent 输出字段要同步下游消费者。
- **改 Remotion 组件后**：跑 `pytest tests/test_m10_remotion.py tests/test_cross_language_contract.py`。
- **提交前**：跑 `pytest`（应全绿，覆盖率门槛 80%）。提交格式见
  `~/.claude/rules/ecc/common/git-workflow.md`（conventional commits）。
- **绝不 commit**：`.env` / `minimax-key.txt` / 真实 key。`.gitignore` 已含。
- **跑管道前**：确认 `remotion/node_modules` 存在（`npm install` 过），否则渲染阶段失败。
- **断点续跑**：`run_full.py` 会加载已有 state，自动重试未完成阶段（retry_count 清零）。
  要重头跑则删 `data/projects/<id>/state.json`。
- **失败排查**：看 `data/projects/<id>/state.json` 各阶段 `status` / `error` 字段，
  以及 `data/projects/<id>/decisions.jsonl` 决策日志。

## 测试

```bash
PYTHONUTF8=1 pytest                                    # 全量
PYTHONUTF8=1 pytest tests/test_m10_remotion.py -v      # 渲染管道
PYTHONUTF8=1 pytest --cov=src --cov-report=term-missing
```
