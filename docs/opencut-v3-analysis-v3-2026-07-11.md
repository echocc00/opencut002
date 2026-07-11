# OpenCut v3.0 重构项目系统性分析与优化建议

> **日期**：2026-07-11
> **范围**：`F:\claudepc\opencut002\opencut-v3\` 核心代码 + 设计规格 + 实施计划
> **目的**：理解项目全貌 → 系统性分析现状 → 给出有理有据的优化建议

---

## 一、项目一句话总结

**目标**：通用领域 AI 短视频生产平台，通过"代码编排 + AI 创作"混合架构稳定输出可与优质手动内容竞争的短视频（先自用验证质量，后产品化）。

**实现路径**：六层架构（交互 → 编排 → Agent → 工具 → 领域配置 → 数据），21 个阶段的 YAML 驱动管道，三种审批模式（手动/半自动/全自动），四道质量关卡，Remotion 替换 FFmpeg FilterGraph 做画面合成，WhisperX 提供词级时间戳。

**能实现的效果**：用户上传图片或粘贴参考视频链接 → 自动选题 → 亮点两阶段拆分 → 文案创作 → 画面匹配 → TTS 生成配音 → 分镜 → 质量关卡 → BGM + 节奏编排 → 标题/封面 → Remotion 渲染 → 自检 → 交付。决策全程留痕，用户偏好和标注回流驱动后续 AI 决策。

---

## 二、代码现状扫描

| 维度 | 实际状况 |
|------|---------|
| Python 源码 | 约 3,368 行，36 个文件分布在 7 个子包 |
| 测试代码 | 约 2,541 行，21 个测试文件，对应 24 个模块的验收 |
| 领域配置 | travel（完整）/ education（部分）/ knowledge_paid（极简）/ custom（仅有 2 个 markdown） |
| Remotion | 11 个 TS/TSX 文件，主题系统 + 4 类场景 + 字幕/音轨/运镜 |
| 数据资产 | highlights.json 6 条；voices.json 8 种音色；research.json 6 模板；opening_templates.yaml 4 类 |
| Pipeline YAML | 21 个阶段已声明 |

### 2.1 子包规模

```
src/
├── orchestrator/   # 编排层（engine, state, contracts, approval, preference）
├── agents/         # 16 个 StageAgent + base + skill_loader + decision_logger + confidence_scorer
├── tools/          # 8 个工具（render/transcribe/audio/image/web/video/scene/migration）
├── quality/        # 4 道关卡（preflight/postflight/slideshow_scorer/post_render_validator）
├── providers/      # selector(7维评分) + provider_registry
├── observability/  # annotation_store + event_store
└── api/            # FastAPI 路由（project + panel）
```

---

## 三、已完成的部分（vs 设计文档 M01-M24）

| 模块 | 状态 | 关键实现 |
|------|------|---------|
| **M01** 项目脚手架 | ✅ | pyproject + Settings（pydantic-settings）+ 目录结构 |
| **M02** 状态管理 | ✅ | StageState / ProjectState / 13 个 Pydantic 契约模型 |
| **M03** 管道引擎 | ✅ | YAML 驱动 + 21 阶段 + 三审批模式 + auto retry |
| **M04** 领域配置层 | ✅ | DomainConfig 加载 style/highlights/voices/research/opening_templates |
| **M05** 技能加载器 | ✅ | SkillLoader 解析 Purpose/Quality Rules/Anti-Patterns/Output Contract/Guidance |
| **M06** StageAgent 框架 | ✅ | BaseStageAgent + execute 流程 + 上游 context 构建 |
| **M07** Provider 评分 | ⚠️ 表面完整 | 7 维度评分从 YAML 加载，但底层 provider 实例是同一个 |
| **M08** 质量治理 | ⚠️ 表面完整 | 4 道关卡实现，但 postflight/preflight 失败只 warn 不阻断 |
| **M09** WhisperX | ✅ | 主路径 + silencedetect fallback |
| **M10** Remotion | ⚠️ 关键能力丢失 | 逐词字幕变成整段字幕 |
| **M11** FFmpeg 音频 | ✅ | mix_bgm_with_ducking + normalize + detect_clipping |
| **M12-M16** 所有 21 个 Agent | ✅ | topic/highlight/copywriting/storyboard/title/cover/render/material/web/tts/voice/bgm/rhythm/fine_cut/image_matching/reference |
| **M17** 审批 + 偏好 | ✅ | should_pause_for_review + PreferenceProfile |
| **M18** 置信度 | ✅ | calculate_confidence + STAGE_REQUIRED_KEYS |
| **M19** 参考视频 | ✅ | video_downloader + scene_detector + reference_analyzer |
| **M20** 监控面板 | ⚠️ 后端有，前端无 | 3 个 GET 路由（status/decisions/quality） |
| **M21** 标注回流 | ✅ | AnnotationStore + 6 正向 + 6 负向标签 + build_guidance_prompt |
| **M22** 资产迁移 | ✅ | migration.py 存在 |
| **M23-M24** E2E + Docker | ⚠️ 部分 | test_e2e_full_pipeline.py 完整；docker-compose.yml 存在但未验证 |

---

## 四、与设计文档的关键偏离 / 功能缺口

### 4.1 🟥 高优先级缺口

| 缺口 | 设计要求 | 实际实现 | 影响 |
|------|---------|---------|------|
| **逐词高亮字幕失效** | 逐词放大/变色/对齐（Remotion 核心卖点） | [WordByWordSubtitle.tsx:17](remotion/src/components/WordByWordSubtitle.tsx) 直接 `words.map(w => w.word).join("")` 显示整段字幕，时间戳字段完全没用到 | 核心差异化能力失效，等于回到 v2 的"整段字幕"，相当于这次重构最大的卖点没兑现 |
| **Provider 多选择是假的** | 7 维度评分选择 doubao/deepseek/qwen | [provider_registry.py:86-89](src/providers/provider_registry.py#L86) 把 minimax 同一实例注册到 4 个名字（"minimax"/"deepseek"/"doubao"/"qwen"）；config/providers.yaml 里的 4 套分数全是纸上谈兵 | 评分选择器在选 4 个相同对象，分数差异无意义，"Provider 选型不确定"这个原始痛点没解决 |
| **API Key 文件硬编码路径** | env 变量管理 | [provider_registry.py:74](src/providers/provider_registry.py#L74) `open("../minimax-key.txt")` | 不利于部署，存在路径假设；安全审计红灯 |
| **缺失前端** | M20 计划"最简前端页面" | 只有 FastAPI 路由，无任何 HTML/JS | 设计规格 11 节生产面板完全未实现 |
| **教育/知识付费/自定义领域实质未完工** | 设计规格 5.1 节要求"新增领域只需新增配置，不改代码" | knowledge_paid 仅有 style.yaml + 2 个 markdown；custom 只有 2 个 markdown；education 没有 research.json 和 voices.json | "领域配置层"承诺的多领域可扩展性目前只是空壳 |
| **Remotion 输入数据文件不清理** | M10 验收标准 | remotion/input_*.json 已有 38 个遗留文件 | 长跑会撑爆目录 |

### 4.2 🟧 中优先级缺口

| 缺口 | 说明 |
|------|------|
| **BGM 库几乎没有** | travel/bgm 目录是空的（文件查找只发现 education/bgm/ambient.mp3 一个），但 BGM 选择 Agent 在跑 |
| **预算治理**：M21 节说"成本追踪（先 observe，后 cap）" | decision_logger 字段 cost 在代码里根本没被填充，state.cost_total 永远是 0 |
| **decision_log 字段缺失** | 规格要求 input_tokens / output_tokens / prompt_skill_file / model | BaseStageAgent.execute 中 decision_logger.log 只传 7 个字段，规格要求 8+ 个 |
| **decision_logger 与 event_store 双轨** | 设计是统一 EventStore；实际两个独立 JSONL 文件 | 同一事件写两份，replay 逻辑分裂 |
| **WhisperX 模型延迟加载缺失** | 每次 Transcriber 实例化时不懒加载，但 _whisperx_model 是 None 占位，CPU 路径会进入 try except fallback | 看起来实现 OK，但 silently 退化无告警 |
| **AI 错误无重试** | TTS、WhisperX、AI provider 调用失败时无重试 | 网络抖动会直接断管道 |
| **3 个 agent 重复文件** | highlight_agent.py 与 highlight_selection_agent.py 内容一致；voice_agent.py 与 voice_selection_agent.py 一致；image_matching_agent.py 重复 | engine 引入 selection 后缀版，但旧文件还存在，容易误导入 |

### 4.3 🟨 低优先级缺口

- TTS 的 fallback 路径生成"静音音频"会让视频无声播放，但 pipeline 不会失败，post_render_check 的 RMS 检测会判定 healthy 通过，bug 被掩盖
- CORS `allow_origins=["*"]` 开发期 OK，生产前必须收紧
- web_searcher 实际只跑 DuckDuckGo，Bing 需要 key 但 sources 字段声明 "bing" 在内
- quality_reports 字段在 state.py 保留，但从未被填充 —— 死字段
- continuity 评分死代码：selector.py 第 99 行 `100 if previous_provider == provider else 50`，但 BaseStageAgent 从未传 previous_provider

---

## 五、架构 / 代码质量系统性问题

### 5.1 引擎层 (`src/orchestrator/engine.py`)

- **职责过载**：350 行单文件，混合了管道驱动、阶段注入（highlight_selection/copywriting/tts/voice/bgm 的 input_data 注入散落在 run 方法里）、quality gate 注册、event 发射
- **多次 import**：engine.py 第 35-50 行 + 第 195-289 行存在多处 `from ..quality.xxx import ...` 和 `from ..config import get_domain_config`，违反 PEP 8（应在模块顶部）；同时每次循环都重复导入，浪费 IO
- **审批耦合混乱**：`should_pause_for_review` 函数只有 21 行，但 engine 里同时有 quality_gate 重试、approve_stage 反向调用 run()，状态机不清晰
- **dry_run 只打印不返回**：第 176-181 行 dry_run 返回了 state 但没保存，调用方容易丢失"演练意图"

### 5.2 Provider 层 (`src/providers/`)

- **同一 Provider 4 个名字**：最严重的诚信问题。如果 4 个 provider 实际是同一 minimax 对象，那 config/providers.yaml 的精细评分矩阵形同虚设
- **selector.py 第 99 行**：`continuity = 100 if previous_provider == provider else 50` —— 但 BaseStageAgent 调 selector 时从未传入 `previous_provider`，永远是 50。死代码
- **score 文件没在评分时被注入**：规格 §8.1 要求"Output Quality: 在类似任务上的历史产出质量"，但历史数据从哪读？没有 history store

### 5.3 数据契约 (`src/orchestrator/contracts.py`)

- 契约 schema 完整（13 个 Pydantic 模型），但 **执行不严**：engine 第 287-291 行 postflight 失败只 log.warning，不阻断；preflight 第 195-198 行同样只 warn；output_ok 为 False 时继续推进，违反了规格 §7.1 "Critical 不通过 = 视频不呈现"
- STAGE_INPUT_SCHEMA 在 preflight.py，但 stage 之间真正传递的 input_data 注入却在 engine.py 里。**两个真理来源**导致契约不同步

### 5.4 Remotion 渲染 (`remotion/src/`)

- **字幕组件名实不符**：[WordByWordSubtitle.tsx](remotion/src/components/WordByWordSubtitle.tsx) 名字是"逐词"，实际是"整段"，**且文件顶部注释自己承认了这点**："消除所有时间同步问题。后续需要逐词高亮时再恢复分页逻辑" —— 这是这次重构最关键能力的放弃声明
- **resolveAsset.ts 第 28 行**：`try { return staticFile(src); } catch { return src }` —— Remotion 的 `staticFile()` 不抛异常，catch 永远进不去
- **Cover/Title/Segment 各自处理弹簧动画，参数不一致**：theme.ts 定义了 springConfig，但 CoverScene 用的是 `theme.springConfig`，没有视觉对比层次
- **Soundtrack 的 fadeIn/fadeOut 是音量函数**：第 23-25 行用 interpolate 算 min(fadeIn, fadeOut)，但 loop=true 时 fadeOut 在最后一帧之前就归 0，与循环起点叠加有瑕疵

### 5.5 数据 / 状态

- ProjectState 用 Pydantic 但没有冻结 —— Engine 内会直接改 stage.status（state.py 第 56 行 `stage.status = status`），违反 common/coding-style.md 的 immutability 原则
- 文件 IO 同步阻塞：state.save 用 `path.write_text()`（同步），3 万行 state.json 会卡顿；高频保存时（每个阶段 3 次 save）累积明显
- state.json 在 state/quality_reports 字段保留，但 quality_reports 从未被任何代码填充 —— 死字段

### 5.6 测试质量

- E2E 测试是好的（test_e2e_full_pipeline.py 覆盖 16 阶段数据流）
- 但 80% 覆盖率要求只是文档声明，没有 CI 强制
- test_e2e_real_provider.py 只有 61 行 —— 真实 provider 跑管道的测试几乎不存在
- Web 渲染 / Remotion 集成测试 test_m10_remotion.py 130 行，但靠 mock subprocess，难以验证真实渲染问题

---

## 六、按优先级排序的优化建议

### 🟥 P0：核心能力失效，必须立刻修

#### 6.1 恢复逐词高亮字幕（最关键的差异化能力）

**问题**：[WordByWordSubtitle.tsx:17](remotion/src/components/WordByWordSubtitle.tsx) 直接 join 所有 word，丢掉了所有时间信息。

**修复方案**（直接照搬设计文档 §9.3 的代码）：

```tsx
// 当前（错的）
const fullText = words.map(w => w.word).join("");

// 应改为
{words.map((w, i) => {
  const isActive = currentTime >= w.start && currentTime <= w.end;
  const isPast = currentTime > w.end;
  return (
    <span key={i} style={{
      color: isActive ? style.activeColor : isPast ? style.pastColor : style.upcomingColor,
      transform: isActive ? `scale(1.15)` : `scale(1)`,
      transition: "transform 0.1s, color 0.1s",
      marginRight: "0.2em",
      display: "inline-block",
    }}>
      {w.word}
    </span>
  );
})}
```

**为什么这是 P0**：规格 §14 明确"渲染表现力不足"是双三角基本功的痛点；这次重构引入 Remotion 的核心理由就是"逐词高亮字幕是刚需"。如果放弃，相当于 5 周 M10 工作全废了。

#### 6.2 修 Provider 多选择是假的

**问题**：[provider_registry.py:86-89](src/providers/provider_registry.py#L86) 同一 minimax 对象注册到 4 个 key。

**两条路**：
- **A. 真接 4 个 provider**：实现 OpenAI 兼容 client 分别连 deepseek / doubao / qwen 的真实 endpoint
- **B. 只暴露 minimax，评分改为"模型 + 路由策略"**：把 config 里的 4 列改为 1 列（minimax）+ 4 种 prompt 风格

**强烈建议 A**，因为 B 是把"假多样性"做成"显式简化"，更诚实。

**附加修复**：
- BaseStageAgent 调用 selector 时传 `previous_provider=self._last_provider`（要存 state）
- 在 selector.py 第 99 行的 continuity 逻辑才能真正起作用

#### 6.3 Render Agent 的 word_timestamps 拼接假设

**问题**：[render_agent.py:38-39](src/agents/render_agent.py#L38) 用 `tts_output.word_timestamps` 按 `seg.time_start ~ seg_end` 切片。但 render_agent 收到的 segments 来自 storyboard，而 storyboard 的 time_start 是相对值（以 0 起），而 word_timestamps 是绝对时间（以音频起点）。如果 storyboard 没收到 TTS 总时长回填（engine 第 207-213 行只在 tts 阶段执行后才填），segments 的 time_start 可能从 0 开始（对的），但全靠运气。

**修复**：在 storyboard 阶段输出后立即对齐一次 time_start 基准。

---

### 🟧 P1：架构诚信问题，不修会被反噬

#### 6.4 严肃对待契约校验（规格 §7.1 的承诺）

当前 preflight/postflight 失败只 warn。规格说 "Critical 不通过 = 视频不呈现"。

**修复**：
- preflight 失败 → 阶段标 PENDING + log error，但不静默
- postflight 失败（schema 校验）→ 阶段进入 RETRY 状态而不是直接 COMPLETED
- engine 区分 warn 级（可继续）和 fail 级（必须 retry）

#### 6.5 状态写入改为不可变 + 异步

- state.py 用 Pydantic `model_copy(update=...)` 替代直接 `stage.status = ...`
- save 改为 async（用 aiofiles，pyproject 已经有依赖）
- engine 引入 debounce：阶段完成才 save（不再每步 save）

#### 6.6 Engine 拆分输入注入

新建 `src/orchestrator/stage_input_injector.py`，把 engine.py 第 200-238 行的所有 `if name == "..."` 块搬过去，引擎只做调度。

**好处**：契约一处定义，避免 preflight 和 engine 注入规则不同步。

#### 6.7 修 BGM/WhisperX/TTS 的 silent failure

- BGM 目录空时，BGM Agent 返回 `candidates=[]`，下游 rhythm 拿到空 candidates 直接拼接失败但被吞掉
- WhisperX fallback 时返回 method="fallback"，调用方 TTS Agent 没检查这个字段就当 80 分
- TTS 失败时 fallback 生成静音，下游 video 是无声但 confidence=80

**修复**：所有 silent failure 都要 log.error 并让 quality gate 看到，否则质量治理就是空话。

#### 6.8 删除重复 Agent 文件

- `highlight_agent.py` 与 `highlight_selection_agent.py` 内容一致，删一个
- `voice_agent.py` 与 `voice_selection_agent.py` 一致，删一个
- 注释里 highlight_agent.py 是 import 入口，标注一下

---

### 🟨 P2：质量提升，批量做

#### 6.9 补完领域配置（否则"新增领域不改代码"是空话）

- `domains/education/`: 补 voices.json + research.json + highlights.json + bgm/ 至少 5 个 mp3
- `domains/knowledge_paid/`: 补完所有（目前只有 2 个 markdown + 1 个 style）
- `domains/custom/`: 补 README 说明如何从 travel 复制改造

**验证标准**：写一个 unit test：从 travel 复制出 mydomain，删除 X 项配置，断言加载报错信息友好。

#### 6.10 decision_logger 字段补全（规格 §8.2 要求 11 个字段）

当前只有 7 个。补：
- `input_tokens` / `output_tokens`（从 provider 响应元数据拿）
- `prompt_skill_file`（从 BaseStageAgent 里 stage.name → domains/{domain}/skills/{stage}.md）
- `model`（从 provider.model 拿）
- `cost`（基于 token + provider 单价）

#### 6.11 EventStore 与 DecisionLogger 合并

两条 JSONL 事件流导致 replay 困难。**建议**：DecisionLogger 改为 emit() 接口，存 events.jsonl 统一一份；现有 decision_log.jsonl 路径保留只读兼容期。

#### 6.12 Remotion 主题层级化

theme.ts 当前把所有动画参数塞在一个 springConfig 里。建议分：
- `enter_spring`（入场）
- `accent_spring`（强调）
- `exit_fade`（退场）
- `caption_spring`（字幕）

不同 domain 在 style.yaml 配不同风格，不必都耦合到 springConfig。

#### 6.13 修 Cost 永远为 0

cost_total 字段从未填充。**修复**：decision_logger.log 加 cost 字段（基于 token × 单价），state.json 累加。

#### 6.14 CORS 收紧

`app.py:15` 当前 `allow_origins=["*"]`，生产前必须改为环境变量驱动的白名单。

---

### 🟩 P3：清理 / 文档

#### 6.15 清理 Remotion input 临时文件

`remotion_renderer.py` 每次渲染生成 `input_<uuid>.json` 不清理。修：
- 渲染成功后移到 `data/projects/{id}/remotion_input.json`
- 失败时清理临时文件

#### 6.16 加 .env.example 完整说明

当前 `.env.example` 仅 289 字节，缺关键变量说明：
- `OPENCUT_DATA_DIR`
- `OPENCUT_REMOTE_BGM_DIR`（如果支持远程 BGM 库）
- `WHISPER_MODEL` / `WHISPER_DEVICE`
- `MINIMAX_API_KEY` / `MINIMAX_API_BASE` / `MINIMAX_MODEL`

#### 6.17 加 CI 强制 ≥80% 覆盖率

pyproject 没声明 coverage 配置；建议加 `[tool.coverage]` 配置，CI 跑 `pytest --cov-fail-under=80`。

#### 6.18 测试真实性

- test_e2e_real_provider.py 加一个"用真实 minimax + mock 出图"的冒烟测试（标记 slow）
- test_m10_remotion.py 至少跑一次真实 10s 视频渲染（标记 manual）

#### 6.19 删除代码里的中文 magic 字符串

比如 `image_matcher.py` 第 13-16 行的中文 prompt 是裸字符串。要么抽到常量 / 翻译资源，要么包成函数 `build_matching_prompt(paragraphs, images)`。

---

## 七、按工作量的优先级矩阵

| 优先级 | 项 | 工作量 | 业务影响 | 风险 |
|--------|-----|--------|---------|------|
| P0-1 | 恢复逐词高亮字幕 | 半天 | 极高（核心差异化） | 低 |
| P0-2 | 修 Provider 多选择 | 1-2 天 | 高（取消虚假差异） | 中 |
| P0-3 | word_timestamps 对齐 | 半天 | 高（修隐蔽 bug） | 低 |
| P1-4 | 契约校验严格化 | 1 天 | 高（兑现规格承诺） | 中 |
| P1-5 | 状态不可变 + 异步 | 1 天 | 中（性能 + 健壮） | 中 |
| P1-6 | Engine 输入注入拆分 | 半天 | 中（架构清晰） | 低 |
| P1-7 | Silent failure 治理 | 1 天 | 高（质量治理核心） | 低 |
| P1-8 | 删重复文件 | 5 分钟 | 低（清洁） | 低 |
| P2-9 | 补完领域配置 | 2-3 天/域 | 中（解锁产品化） | 低 |
| P2-10 | decision_logger 字段 | 半天 | 中（审计完整） | 低 |
| P2-11 | 合并 EventStore | 1 天 | 中（可观测性） | 中 |
| P2-12 | 主题层级化 | 1 天 | 中（视觉调优） | 低 |
| P2-13 | Cost 字段填充 | 半天 | 低（成本治理前置） | 低 |
| P2-14 | CORS 收紧 | 5 分钟 | 低（安全） | 低 |
| P3-15 | 清理 Remotion input | 5 分钟 | 低（清洁） | 低 |
| P3-16 | .env.example | 半小时 | 低（部署） | 低 |
| P3-17 | CI 覆盖门槛 | 1 小时 | 低（质量门） | 低 |
| P3-18 | 真实 provider 测试 | 1 天 | 中（信心） | 低 |
| P3-19 | 抽 magic string | 1 天 | 低（可维护） | 低 |

**累计**：P0 + P1 ≈ 6-7 个工作日；P2 ≈ 1-2 周；P3 ≈ 1 周。

---

## 八、最终建议

**先做 3 个 P0**：逐词高亮（产品差异化的命根子）、Provider 真实化（取消架构欺骗）、word_timestamps 对齐（修一个隐蔽但影响全局的 bug）。三件事加起来不超过 3 个工作日，会立刻让 v3.0 从"看起来能跑"升级到"产出质量立得住"。

**然后 4 个 P1**：让规格 §7 质量治理的承诺不再只是 warn 日志。这部分是"质量优先"哲学的兑现，做完后 v3 才真正进入"能与优质手动内容竞争"的区间。

**P2/P3 按团队节奏推进**：领域配置和决策日志字段补全是产品化前的硬性前提，建议并行排期。

---

## 九、整体评价

- ✅ **架构骨架**（六层 + 三审批模式 + 四关卡）落地质量比设计预期好
- ⚠️ **测试覆盖**和**契约治理**比规格预期弱
- ❌ **最严重的失败**是放弃逐词字幕和 Provider 多选择造假两个点

这两个点不修，v3 就还是 v2 的换皮。逐词字幕是这次重构的"为什么做 Remotion"的答案；Provider 多选择是这次重构的"为什么做评分选择器"的答案。两个答案都名存实亡，是当前最需要补的两个洞。

---

## 附录：关键文件索引

| 文件 | 行数 | 职责 | 状态 |
|------|------|------|------|
| [src/orchestrator/engine.py](src/orchestrator/engine.py) | 350 | 管道调度 + 阶段注入 + 质量门 | ⚠️ 职责过载 |
| [src/orchestrator/state.py](src/orchestrator/state.py) | 81 | 项目状态 + 持久化 | ⚠️ 非不可变 |
| [src/agents/base_agent.py](src/agents/base_agent.py) | 116 | Agent 框架 + skill/prompt/provider 编排 | ✅ |
| [src/providers/selector.py](src/providers/selector.py) | 138 | 7 维度评分 | ⚠️ continuity 死代码 |
| [src/providers/provider_registry.py](src/providers/provider_registry.py) | 90 | Provider 注册 | ❌ 4 选 1 假象 |
| [src/quality/slideshow_scorer.py](src/quality/slideshow_scorer.py) | 155 | 6 维度风险评分 | ✅ |
| [src/quality/post_render_validator.py](src/quality/post_render_validator.py) | 189 | 渲染后自检 | ✅ |
| [src/agents/skill_loader.py](src/agents/skill_loader.py) | 81 | Markdown 技能解析 | ✅ |
| [src/agents/confidence_scorer.py](src/agents/confidence_scorer.py) | 107 | 规则评分 + AI 自评加权 | ✅ |
| [src/agents/render_agent.py](src/agents/render_agent.py) | 103 | Remotion 渲染入口 | ⚠️ time_start 对齐假设 |
| [src/agents/tts_agent.py](src/agents/tts_agent.py) | 68 | TTS + WhisperX 串联 | ⚠️ silent failure |
| [src/tools/remotion_renderer.py](src/tools/remotion_renderer.py) | 116 | Python→Remotion 桥接 | ⚠️ 不清理临时文件 |
| [src/tools/audio_processor.py](src/tools/audio_processor.py) | 81 | BGM 混音 + 归一化 + 削波 | ✅ |
| [src/tools/transcriber.py](src/tools/transcriber.py) | 138 | WhisperX + fallback | ⚠️ 退化无告警 |
| [remotion/src/VideoComposition.tsx](remotion/src/VideoComposition.tsx) | 86 | 顶层组合 | ✅ |
| [remotion/src/scenes/SegmentScene.tsx](remotion/src/scenes/SegmentScene.tsx) | 103 | 分镜画面 | ✅ |
| [remotion/src/components/WordByWordSubtitle.tsx](remotion/src/components/WordByWordSubtitle.tsx) | 54 | 字幕 | ❌ 名实不符 |
| [remotion/src/theme.ts](remotion/src/theme.ts) | 83 | 主题系统 | ⚠️ springConfig 单层 |
| [remotion/src/utils/cameraMotion.ts](remotion/src/utils/cameraMotion.ts) | 61 | 8 种运镜 | ✅ |
| [remotion/src/utils/resolveAsset.ts](remotion/src/utils/resolveAsset.ts) | 33 | 路径解析 | ⚠️ catch 永不触发 |
| [config/providers.yaml](config/providers.yaml) | 89 | 4 个 provider × 7 维度分数 | ⚠️ 对应 1 个真实 provider |
| [pipelines/default.yaml](pipelines/default.yaml) | 79 | 21 阶段管道定义 | ✅ |
| [domains/travel/style.yaml](domains/travel/style.yaml) | 35 | 文旅主题配置 | ✅ |
| [domains/travel/highlights.json](domains/travel/highlights.json) | 10 | 6 条亮点归类 | ✅ |
| [domains/travel/voices.json](domains/travel/voices.json) | 10 | 8 种音色 | ✅ |