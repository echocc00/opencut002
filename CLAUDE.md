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

## 文案驱动模式（script-first）

默认是「素材驱动」：素材 -> AI 生成文案 -> 匹配素材 -> 出片。
另支持「文案驱动」：用户给文案 + 素材池 -> 跳过选题/亮点/AI文案 -> 自动匹配素材池 -> 出片。

```bash
python scripts/run_full.py --script-file <文案.txt> \
  --materials-dir <素材池目录> --project-id <id> --domain education
```

- 用 `pipelines/script_first.yaml`（跳 web_research/topic/highlight，copywriting 改用 `ScriptInputAgent`）
- `ScriptInputAgent` 把用户文案按句号切成 ≤40 字段落，赋默认字段，塞进 copywriting 输出
- `image_matching` 照常把文案段落匹配到素材池图；匹配不上的段落复用池图（render 兜底 `material_files[i % len]`）
- 后续 TTS/分镜/渲染/字幕分块/人脸遮盖全部复用
- 兜底增强（Pexels 搜图 / AI 生图，opt-in）留扩展点，后续按需加

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
api/        HTTP 入口（FastAPI，projects/panel）
orchestrator/  管道引擎 + 状态 + 审批 + 质量关卡
agents/     20 个阶段 Agent（每个阶段一个）
tools/      领域无关工具（TTS / Remotion 渲染 / 图像匹配 / 素材准备）
providers/  多 LLM provider 适配（minimax / doubao / deepseek / qwen）
config.py   领域配置加载（domains/<domain>/）
data/       项目状态与产物（data/projects/<id>/）
```

跨语言数据契约（Python → Remotion）见 [docs/data-flow-contract.md](docs/data-flow-contract.md)。
**改任何渲染数据字段前必读此文档**：Python 侧 snake_case，Remotion 侧 camelCase，
转换在 `RemotionRenderer.build_render_data()`。

## 分支策略（双方向维护）

本分支 `main` = **CLI/agent 版**（精简，agent 调 `scripts/run_full.py` 本地出片，无 web/DB/auth）。
SaaS/私有化方向在 `saas` 分支（含 `web/` + `src/db/` + auth/jobs/key 池）。

- **共同需求**（新领域、管道修复、TTS/渲染改进等）：提到 `main` -> 在 `saas` 上 `git cherry-pick <commit>`（**不要 `git merge main`**：main 的 split commit 会删 SaaS 文件 + 还原共享文件，破坏 saas）。两方向都拿到。
- **SaaS 专属**（web/auth/计费/任务层/key 托管）：只提 `saas`，不进 `main`。
- **拉取**：`git clone -b main <repo>`（CLI 版）或 `git clone -b saas <repo>`（SaaS 版）。
- **永远不把 `saas` 合回 `main`**（会把 SaaS 文件带进精简版）。
- **版本**：CLI 版 tag `v0.x.0-cli`，SaaS 版 tag `v0.x.0-saas`（在 saas 分支）。共同改动两版一起升。

## 领域

内置 4 个：`education` / `travel` / `knowledge_paid` / `custom`（模板）。
每个领域目录含：`style.yaml` / `highlights.json` / `voices.json` / `research.json` /
`opening_templates.yaml` / `bgm/*.mp3` / `skills/*.md`（各阶段 prompt 指导）。

新增领域：复制 `domains/custom` 或 `domains/travel`，改配置 + 换 BGM。详见
[domains/custom/README.md](domains/custom/README.md)。

## 自定义音色（音色复刻，可选）

用 minimax voice cloning 克隆自定义音色：

1. 准备参考音频（mp3/wav，10-30s 清晰人声）
2. 克隆：`python scripts/clone_voice.py --audio <参考音频> --voice-id <自定义ID>`
3. 配到 `domains/<domain>/voices.json`：`{"my_voice": {"name": "我的克隆音色", "minimax_voice_id": "<自定义ID>", "description": "..."}}`
4. 管道 voice_selection 可选该音色，TTS 用克隆音色（支持 emotion 语气）

## 已知坑（务必遵守）

1. **Windows 编码**：控制台默认 GBK，中文/emoji 会 `UnicodeEncodeError`。
   `run_full.py` 已强制 UTF-8；跑测试前设 `PYTHONUTF8=1`。

2. **Remotion 禁用 file://**：无头 Chrome 不允许 `file://` 加载本地资源。
   `render_agent` 自动把素材拷到 `remotion/public/<project_id>/` 解决。
   不要在渲染数据里塞绝对路径，用相对项目根的路径。

3. **TTS 用 minimax 同步 t2a_v2**：响应 `data.audio` 是 hex MP3，Bearer 鉴权，无轮询
   （曾用 t2a_async_v2 + retrieve 轮询，retrieve 在部分账号要 GroupId、Bearer 返回 2013 超时）。
   逐段合成 → ffprobe 探时长 → ffmpeg concat 拼接。TTS 是时间源，不做转写对齐。

4. **素材分析必须用多模态视觉**：文本 LLM 看不见图，会幻觉（把教室说成雪山）。
   `material_analysis_agent` 优先 minimax M3 多模态，doubao 次之，不要回退到纯文本 provider。

5. **素材支持图片 + 视频**：`run_full.py` 经 `material_prep.prepare_materials`
   收录 `*.jpg/*.jpeg/*.png` 图片 + `*.mp4/*.mov/*.avi/*.mkv/*.webm/*.m4v` 视频
   （ffmpeg 自动每 5 秒抽一帧到 `.frames/<stem>/`），取前 5 张。ffmpeg 不在时跳过视频
   仅用图片。图片优先于视频抽帧排序。

6. **字幕是整段淡入**：不逐词高亮。句子-画面对齐由段落级 TTS 时长保证
   （1 段文案 = 1 段 TTS = 1 个分镜段）。改字幕组件见
   `remotion/src/components/WordByWordSubtitle.tsx`。

7. **doubao 模型 ID**：用 `doubao-seed-2-0-lite-260428`，不是显示名
   `Doubao-Seed-2.0-lite`（会 404）。

8. **AI 输出包 xxx_plan 命名空间**：AI 偶发把整个输出包在 `rhythm_plan` / `storyboard_plan`
   等字段里，导致下游 preflight 找不到 `segment_timings` 等顶层字段而 ERROR。
   `base_agent._flatten_plan_namespace` 自动展平 `xxx_plan` -> 顶层，无需各 stage 单独处理。

9. **AI 生成标识（合规储备，默认关）**：设 `OPENCUT_AI_LABEL=1` 开启渲染右下角「AI 生成」
   角标（`remotion/src/components/AiLabel.tsx`）。国内《AI内容标识办法》2025-09-01 生效后
   B2C 公网上线需开启；B2B 私有化部署可不开。`render_agent._ai_label_enabled()` 读环境变量。

10. **字幕单行 ≤16 字分块轮播**：`WordByWordSubtitle.tsx` 把段字幕按标点切成 ≤16 汉字字符的块，
    段内 even-split 轮播（用 `useVideoConfig().durationInFrames` 算段长），单行 60px 字号。
    段级同步不变（段=TTS=音频=画面）；块与语音近似对齐（±0.3s）。切分逻辑在
    `remotion/src/utils/splitSubtitle.ts`。

11. **人脸遮盖（opt-in，默认关）**：设 `OPENCUT_FACE_MASK=1` 开启。`src/tools/face_masker.py`
    用 opencv YuNet 检测素材图所有人脸，可爱贴纸（`src/tools/stickers/*.png`，openmoji）bake 进图，
    产出 `<stem>.masked.jpg`。`render_agent._stage_asset` 优先用 masked 副本（material_analysis
    用原图，render 用贴纸图）。贴纸随 Ken Burns 缩放自然对齐。需装 `[face]` extras：
    `pip install -e ".[face]"`（opencv-python + Pillow）。模型 `src/tools/models/yunet.onnx`。

12. **素材分层兜底（文案驱动缺口处理）**：`image_matching` 按 AI 匹配度 s 分层：
    s≥0.7 直接用匹配池图；0.4≤s<0.7 第1层弱匹配复用；s<0.4 缺口 -> 第2层文字卡
   （`TextCardScene`，无图）或第3层生图（`src/tools/image_generator.py`，opt-in
    `OPENCUT_IMAGE_GEN=1`，minimax image-01，prompt=段落内容+池风格描述）。生图触发：
    缺口≥3 或占比≥40%。阈值 + 开关全 env 可调（`OPENCUT_MATCH_STRONG/WEAK/GEN_TRIGGER_COUNT/
    GEN_TRIGGER_RATIO/IMAGE_GEN`）。每段决策写 `image_matching` 输出 `layer_log` 便于观测调参。

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
