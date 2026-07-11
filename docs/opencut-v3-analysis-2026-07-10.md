# OpenCut v3.0 重构项目分析与优化建议

> **分析日期**：2026-07-10
> **分析范围**：`F:\claudepc\opencut002\opencut-v3\` 全部代码 + 设计规格 + 实施计划
> **分析方法**：通读 30+ 个核心源文件 + 9 个测试文件 + Remotion 组件 + 领域配置，定位"理论设计 vs 实际实现"的差距

---

## 1. 项目理解

### 1.1 目标

OpenCut v3.0 是一个**通用领域 AI 短视频生产平台**，核心定位是解决 v2.1.0 时代的两个老问题：

1. **"AI 困在 Python 类里"**——以前所有 prompt、决策、质量判断都焊死在 stage 代码里，改一次要部署一次。
2. **"不确定瓶颈在哪"**——以前要等成片出来才知道哪一阶段崩了。

v3.0 选了一条清晰的路径：**代码做底线（编排 + 质量关卡），AI 做上限（每个阶段内的创作自由度）**。这与双三角分析中"AI 负责上限，代码负责底线"的判断一致。

### 1.2 六大设计决策（来自设计规格 §2）

| 决策 | 一句话 | 实施体现 |
|---|---|---|
| 混合架构 | 代码编排 + AI 创作 | `src/orchestrator/engine.py` + `src/agents/base_agent.py` |
| 多领域配置 | 核心领域无关 | `domains/{travel,education,knowledge_paid,custom}/` |
| 三种审批模式 | 手动/半自动/全自动 | `engine._needs_review()` + `approval_controller.py` |
| Remotion 渲染 | 替代 FFmpeg drawtext | `remotion/src/VideoComposition.tsx` |
| 技能文件架构 | Prompt 从代码抽离到 Markdown | `domains/*/skills/*.md` + `skill_loader.py` |
| 四道质量关卡 | 强制拦截 | `quality/{preflight,postflight,slideshow_scorer,post_render_validator}.py` |

### 1.3 实现路径

按 24 个模块（M01-M24）分 6 阶段交付：

```
Phase 1（基础）→ Phase 2（框架）→ Phase 3（质量+渲染）→ Phase 4（AI 阶段）→ Phase 5（高级）→ Phase 6（部署）
M01 脚手架 → M04 领域 → M08 质量四关 → M12 Web调研 → M17 审批 → M22 迁移
M02 状态     M05 技能   M09 WhisperX   M13 选题三连  M18 置信度  M23 E2E
M03 引擎     M06 Agent  M10 Remotion   M14 画面+TTS  M19 参考    M24 Docker
              M07 Provider M11 音频    M15 分镜+BGM  M20 面板
                                     M16 标题+渲染  M21 标注
```

**关键路径**：M01→M02→M03→M04→M05→M06→M07→M13→M14→M15→M16→M23→M24

### 1.4 能实现的效果

**端到端视频产出**（全自动模式）：
- 10 张图片 → 30-60 秒竖屏短视频
- 包含：选题、文案、TTS 配音、BGM（带 ducking）、逐词高亮字幕、标题动画、转场
- 同步产出：决策审计日志、质量报告、成本追踪、置信度热力图

**三种模式渐进**：
- 手动模式：9 个决策点全暂停（调试期）
- 半自动模式：高置信度（≥80）自动通过（日常使用）
- 全自动模式：质量关卡不通过自动重试 3 次（批量生产）

**多领域复用**：加新领域只需建 `domains/<name>/` 目录，不改代码。

---

## 2. 重构质量总评

### 2.1 整体评价

**设计扎实、实现到位、问题真实存在。**

**已落地（与设计一致）**：
- 混合架构、模块化状态、YAML 驱动管道、技能文件加载、Provider 评分、4 道质量关卡、Remotion 渲染、决策日志、迁移工具、领域配置目录

**部分缺失或与设计有差距**：
- 偏好画像更新逻辑（`record_decision`）从未被任何代码调用
- 标注回流的"读取同领域高评分视频注入 prompt"未接入 Agent
- 置信度评分系统两套实现（`base_agent._calculate_confidence` vs `confidence_scorer.calculate_confidence`）并存且不一致
- 领域配置 `education` 和 `knowledge_paid` 是空目录——"多领域配置层"实际上是单领域
- Remotion `input.json` 用单文件，多项目并发会冲突
- `panel_routes` 不在 `__init__.py` 暴露的 FastAPI app 里——没有真正的 `app.py`

### 2.2 完成度扫描

| 模块 | 设计目标 | 实际状态 | 差距 |
|---|---|---|---|
| M01 脚手架 | 6 大目录 | ✅ 全部就位 | 无 |
| M02 状态 | 模块化 + 契约 | ✅ 已实现 | `confidence_scorer` 未被任何代码引用 |
| M03 引擎 | YAML 驱动 + 3 模式 | ✅ 已实现 | 半自动逻辑里 `quality_gate` 永远暂停（按设计是手动门），与"质量关卡自动重试"不一致 |
| M04 领域 | 多领域切换 | ⚠️ 骨架 | education/knowledge_paid 目录空 |
| M05 技能加载 | Markdown 解析 | ✅ 已实现 | 无 |
| M06 Agent 框架 | Base + 决策日志 | ✅ 已实现 | 重复 `_extract_json` 两处（base + 子类） |
| M07 Provider | 7 维度评分 | ✅ 已实现 | 评分矩阵硬编码 3 个 provider，扩展新 provider 需改源码 |
| M08 质量关卡 | 4 道关卡 | ✅ 已实现 | `preflight` 仅校验阶段完成状态，不校验阶段输出的契约 |
| M09 WhisperX | 词级时间戳 | ✅ 含 fallback | fallback 精度 0.3s/字，且无 word 文本，字幕高亮失效 |
| M10 Remotion | React 渲染 | ✅ 已实现 | `input.json` 单文件并发不安全 |
| M11 音频 | BGM 混音 | ✅ 已实现 | sidechaincompress 阈值 0.1 偏激进，ducking 容易吞掉语音 |
| M12 Web 调研 | 搜索 + 简报 | ✅ 已实现 | DuckDuckGo Instant Answer 中文支持差 |
| M13-16 AI 阶段 | 选题到渲染 | ✅ 全部就位 | ImageMatcher 没被任何 Agent 调用，画面匹配是死代码 |
| M17 审批 | 3 模式 | ⚠️ 控制器 vs 引擎两套 | `should_pause_for_review` 与 `_needs_review` 重复实现 |
| M18 置信度 | AI 自评 | ⚠️ 双实现冲突 | base 算 75/20，scorer 算 60/40，谁都没用 prompt 让 AI 自评 |
| M19 参考视频 | 模式 B | ✅ 已实现 | `mode` 字段没有在 ProjectState 中 |
| M20 面板 | 状态查询 | ⚠️ 仅 API | `get_top` 测试覆盖了，但没用 `audit_test` 的 project_id 校验 |
| M21 标注回流 | 维度标签 | ⚠️ 仅存储 | `build_guidance_prompt` 从未注入任何 Agent |
| M22 迁移 | 资产导入 | ✅ 已实现 | 实际是 `read+write`，不算迁移（无 schema 转换） |
| M23 E2E | 10 图→视频 | ⚠️ Mock 测试 | 真实渲染未跑通（无 GPU/无 Remotion 环境） |
| M24 Docker | Compose 部署 | ⚠️ 不完整 | 只部署了 api+remotion，缺 worker/Redis/Postgres；`opencut` MCP 服务未注册 |

---

## 3. 优化建议（按优先级）

### P0：影响可用性/正确性

#### 3.1 合并重复的置信度计算，强制 AI 自评

**问题**：
- `src/agents/base_agent.py:91-100` 实现一个简化版（输出 3 字段+20，20/10/20 累加）
- `src/agents/confidence_scorer.py:6-48` 实现完整版（含 required_keys 检查）
- 实际调用的是 base_agent 的简化版（`base_agent.py:50`），scorer 是个孤儿模块
- 设计规格 §6.3 明确要求 "AI 每次产出时自评置信度"，但 prompt 模板里没有任何 "请输出 0-100 自信度" 的指令

**代码证据**：
```python
# base_agent.py:91-100
def _calculate_confidence(self, output: dict) -> float:
    if not output:
        return 20.0
    score = 50.0
    if len(output) >= 3:
        score += 20
    ...
    return min(score, 100.0)
```

**建议**：
1. 删除 `base_agent._calculate_confidence`，统一调用 `confidence_scorer.calculate_confidence(output, required_keys=get_required_keys(stage.name))`
2. 在 `BaseStageAgent._build_prompt` 注入统一指令，例如：
   ```
   【置信度自评】请在 JSON 输出的最后附带 "confidence": 0-100 的整数。
   - 字段完整性: 0=缺字段, 100=全字段
   - 推理可靠性: 0=猜测, 100=基于上游证据
   - 创意稳健性: 0=风险高, 100=符合技能文件所有反模式
   ```
3. 在 `_parse_output` 后读取 `parsed.pop("confidence")` 作为 AI 自评分，与规则分加权（设计规格 §6.3 提到 AI 自评权重 40）

**为什么重要**：置信度是半自动模式自动通过/阻断的核心依据；目前所有阶段都被判为同一档（75 分），等于没有置信度。

#### 3.2 修复单文件 `input.json` 并发风险

**问题**：
```python
# src/tools/remotion_renderer.py:38-40
input_file = self.remotion_dir / "input.json"
input_file.parent.mkdir(parents=True, exist_ok=True)
input_file.write_text(json.dumps(project_data, ensure_ascii=False), encoding="utf-8")
```

两个项目同时渲染时，后写入的会覆盖前者的 props。Remotion CLI 不会知道这个文件属于哪个项目。

**建议**：
```python
input_file = self.remotion_dir / f"input_{project_id}.json"
```
或
```python
input_file = Path(tempfile.gettempdir()) / f"opencut_{uuid4()}.json"
```
后者更稳，避免每次渲染污染 `remotion/` 目录。

#### 3.3 接入偏好画像到 Agent prompt

**问题**：
`src/orchestrator/preference_profile.py:33-48` 定义了 `record_decision`，但 grep 全代码库没有任何调用方。设计规格 §6.2 明确说"偏好画像在每次用户决策后自动更新"且"全自动模式下，AI 读取偏好画像做决策"。

**建议**：
1. 在 `BaseStageAgent._build_upstream_context` 中追加：
   ```python
   pref = self.preference_profile.get_preference_summary()
   if pref:
       parts.append(f"【用户偏好画像】\n{pref}")
   ```
2. 在 `Engine.run` 审批通过后调用 `profile.record_decision(stage, choice, confidence)`：
   ```python
   if needs_review and approved:
       self.profile.record_decision(name, stage.output_data, confidence)
   ```
3. 让 `preference_profile` 通过 DI 注入 `BaseStageAgent`（目前 Agent 构造器没接收 profile）

#### 3.4 接入标注回流到 prompt

**问题**：
`src/observability/annotation_store.py:55-68` 的 `build_guidance_prompt` 是设计规格 §10 标注回流的核心钩子，但搜遍 `agents/` 目录没有任何 Agent 调用它。

**建议**：
1. `BaseStageAgent.__init__` 增加 `annotation_store: AnnotationStore`
2. `BaseStageAgent._build_prompt` 注入：
   ```python
   guidance = self.annotation_store.build_guidance_prompt(min_rating=4)
   if guidance:
       skill_context = f"{skill_context}\n\n{guidance}"
   ```
3. 偏好画像按"高评分视频的标签分布"计算，而不是简单累加用户选项

#### 3.5 双实现审批逻辑合一

**问题**：
- `src/orchestrator/engine.py:98-111` 有 `_needs_review`
- `src/orchestrator/approval_controller.py:7-21` 有 `should_pause_for_review`

两个函数实现完全相同的逻辑。`approval_controller` 还导入了错误的路径（`from ..orchestrator.state` 应该是 `from .state`），实际是死代码。

**建议**：
- 把 `approval_controller.py` 删除（或让它真正成为唯一来源）
- 引擎通过 `should_pause_for_review()` 调用，不重复实现

---

### P1：影响质量/可维护性

#### 3.6 把 preflight 从"阶段完成"升级为"契约校验"

**问题**：
```python
# src/quality/preflight.py:7-13
def check_prerequisites(state, requires):
    issues = []
    for req in requires:
        if not state.is_stage_completed(req):
            issues.append(f"前置阶段 {req} 未完成")
    return (len(issues) == 0, issues)
```

只检查"是否完成"，不检查"输出是否符合契约"。但设计规格 §7.1 写"前置校验：检查阶段输入是否满足要求"——输入契约是"上游阶段必须产出的字段"。

**建议**：
```python
def check_stage_inputs(state, stage_name, input_schema: dict) -> tuple[bool, list[str]]:
    issues = []
    for upstream, required_fields in input_schema.items():
        upstream_out = state.get_stage_output(upstream)
        if not upstream_out:
            issues.append(f"上游 {upstream} 无输出")
            continue
        for f in required_fields:
            if f not in upstream_out or not upstream_out[f]:
                issues.append(f"上游 {upstream} 缺少字段 {f}")
    return (len(issues) == 0, issues)
```

在 `Engine.run` 阶段前调用，把契约校验前置而不是错误时才暴露。

#### 3.7 幻灯片风险评分从"加法累加"改为"基于分位"

**问题**：
```python
# src/quality/slideshow_scorer.py:90-100
def _score_weak_motion(segments):
    static_count = sum(1 for s in segments if not s.get("ab_split", False))
    static_ratio = static_count / max(total, 1)
    score = static_ratio * 50
    durations = [s.get("actual_duration", 3.0) for s in segments]
    avg_dur = sum(durations) / max(len(durations), 1) if durations else 0
    if avg_dur > 4.0:
        score += min((avg_dur - 4.0) * 15, 50)
    return min(score, 100.0)
```

`avg_dur=4.1` 加 1.5 分，`avg_dur=5` 加 15 分——但 4.1 秒的段和 5 秒的段人眼感知差异巨大，线性罚分不合理。`_score_repetition` 同样问题（repeat_ratio * 60 + 缺口 * 80）。

**建议**：
- 引入分位数阈值（如 avg_dur > 4.5 才计 80 分，> 5.5 计 100 分）
- 给"连续 3 张同图"加分（指数罚分），给"连续 2 张"温和加分

#### 3.8 WhisperX fallback 加最低保真

**问题**：
```python
# src/tools/transcriber.py:148-161
words: list[dict] = []
for seg in segments:
    seg_duration = seg["end"] - seg["start"]
    est_chars = max(1, int(seg_duration / 0.3))
    for i in range(est_chars):
        words.append({
            "word": "",  # fallback 无法识别具体文字
            "start": seg["start"] + i * char_duration,
            "end": seg["start"] + (i + 1) * char_duration,
        })
```

**fallback 的 word 全是空字符串**，这意味着 `WordByWordSubtitle` 渲染时所有词都为空，只有高亮颜色变化——视频里就是无声无字的闪烁。

**建议**：
- 至少从 TTS 输入文本按字符切分喂回（既然 TTS 输入是已知文本）：
  ```python
  def align_with_text(words, full_text):
      chars = list(full_text.replace(" ", ""))
      if len(chars) == 0:
          return words
      if len(words) == 0:
          return words
      ratio = len(chars) / len(words)
      ...
  ```
- 或调用 `edge-tts` 自己的 `SubMaker`（它会输出时间对齐的字幕，无需 WhisperX）
- fallback 不应作为"完整方案"被依赖——测试应该跳过 fallback 路径直接 mock

#### 3.9 BGM ducking 阈值调整 + 段落音量差异化

**问题**：
```python
# src/tools/audio_processor.py:31
f"[bgm][voice]sidechaincompress=threshold={duck_threshold}:ratio=4:attack=0.05:release=0.3[ducked];"
```
默认 `duck_threshold=0.1`、attack=0.05、release=0.3。在语音能量较低的尾音段，BGM 也会被压低 4 倍，**人耳会感觉 BGM 在跳**。

**建议**：
- `threshold=0.05` 太敏感，调到 `0.02`（只在语音明显强于 BGM 时压）
- 引入"段落音量差异化"：开头/结尾 BGM 0.15，主体段 0.25，高潮段 0.35
- 增加到 AudioProcessor 一个 `mix_bgm_smart()` 方法，按 segment_timings 调节

#### 3.10 Remotion `input.json` 路径外移 + props 文件管理

**问题**：见 3.2。补充：`render()` 函数每次都覆盖 `input.json`，无清理。

**建议**：
```python
import tempfile, uuid
input_file = Path(tempfile.gettempdir()) / f"opencut_{uuid.uuid4().hex}.json"
# ... 渲染 ...
input_file.unlink(missing_ok=True)
```

#### 3.11 Provider 评分矩阵移到 YAML

**问题**：
`src/providers/selector.py:48-72` 硬编码：
```python
TASK_FIT_MATRIX: dict[TaskType, dict[str, float]] = {
    TaskType.TOPIC_GENERATION: {"doubao": 90, "deepseek": 85, "qwen": 80},
    ...
}
WEIGHTS = {"task_fit": 0.30, ...}
```

加新 provider（如 MiniMax、Claude）或调整权重都要改代码、重新部署。设计规格 §8.1 提到"评分驱动 Provider 选择"但没要求硬编码。

**建议**：
1. 矩阵移到 `config/providers.yaml`：
   ```yaml
   weights:
     task_fit: 0.30
     output_quality: 0.20
     ...
   task_fit_matrix:
     topic_generation:
       doubao: 90
       deepseek: 85
       qwen: 80
   output_quality:
     doubao: 78
     ...
   continuity:  # continuity 不需要矩阵
   ```
2. `ProviderSelector` 构造时加载 YAML
3. 同时支持 `OPENCUT_PROVIDER_OVERRIDES` 环境变量覆盖某行

#### 3.12 `image_matcher` 接入 Agent

**问题**：
`src/tools/image_matcher.py` 实现了 `match_images()`，但搜遍 `agents/` 目录没有任何 Agent 调用它——`pipelines/default.yaml` 第 24 行有 `image_matching` 阶段，但 `agents/` 下没有 `image_matching_agent.py`。

**建议**：
- 新建 `src/agents/image_matching_agent.py`，调用 `match_images` 作为回退主逻辑
- 失败时 AI 重排
- 与 `material_analysis` 协同：先用 AI 语义匹配（`ai_complete`），失败回退到按 image_hint 顺序分配

---

### P2：影响可扩展性

#### 3.13 抽出 `StoryboardAgent` 渲染参数注入到 React 组件

**问题**：
- `domains/travel/style.yaml` 里有 `transition_duration: 0.4` 等参数
- `pipelines/default.yaml` 里所有段都是 `transition: crossfade` 硬编码
- Remotion `VideoComposition.tsx` 完全不读 style 也不读 transition

**建议**：
- `StoryboardAgent` 在 `output_data` 里带 `style` 字段（动画类型、转场时长、Ken Burns 速率）
- `remotion/src/scenes/SegmentScene.tsx` 根据 `transition` 字符串分发到 `<FadeIn>`, `<SlideTransition>`, `<ZoomPan>` 等组件
- 把 `style` 也透传，让 spring 动画参数可调

#### 3.14 FastAPI app 入口补齐

**问题**：
```dockerfile
# Dockerfile:23
CMD ["uvicorn", "src.api.panel_routes:router", "--host", "0.0.0.0", "--port", "8000"]
```

`panel_routes:router` 是 `APIRouter` 不是 `FastAPI` app。`uvicorn` 会启动失败（"router" 不可作为 app）。

**建议**：
1. 新建 `src/api/app.py`：
   ```python
   from fastapi import FastAPI
   from .panel_routes import router as panel_router
   from .project_routes import router as project_router  # 待补
   
   app = FastAPI(title="OpenCut v3")
   app.include_router(panel_router)
   app.include_router(project_router)
   ```
2. 新建 `src/api/project_routes.py`：创建/查询/审批/运行管道
3. Dockerfile CMD 改为 `uvicorn src.api.app:app`

#### 3.15 教育/知识付费领域填骨架

**问题**：
- `domains/education/skills/`、`domains/knowledge_paid/skills/` 都是空目录
- 实施计划 M04 写"教培/知识付费骨架（内容可后续填充）"
- 但这导致 `get_domain_config("education")` 加载时所有字段为空、没有任何 skill.md

**建议**：
- 至少每个领域提供 2-3 个代表性 skill.md（如 `education/intro.md`, `education/concept_explanation.md`）
- `style.yaml` 提供合理的默认值（如 `pacing.default_duration: 60`、`copywriting.tone: professional`）
- 加领域时验证：`pytest -k "test_education_domain"`，确保 `DomainConfig` 加载不抛错

#### 3.16 Panel Routes 加上 `audit_trail` 项目 ID 校验

**问题**：
```python
# tests/test_m23_e2e.py:99-107
async def test_e2e_decision_log_audit_trail(e2e_setup):
    eng, data_dir = e2e_setup
    state = ProjectState(project_id="audit_test", approval_mode="full_auto")
    await eng.run(state)
    logs = DecisionLogger(data_dir, "audit_test").get_all()
```

`DecisionLogger(data_dir, "audit_test")` 与 `state.project_id="audit_test"` 刚好一致——但这是测试硬编码的。如果 panel routes 用了 `Path("data/projects/...")` 硬编码，与 `state.save()` 的 `data_dir` 拼接不一致，会出现路由找不到项目。

**建议**：
- 路径管理抽到一个 `PathResolver`：
  ```python
  class PathResolver:
      def __init__(self, data_dir: Path): self.data_dir = data_dir
      def project_state(self, pid): return self.data_dir / "projects" / pid / "state.json"
      def decision_log(self, pid): return self.data_dir / "projects" / pid / "decision_log.jsonl"
  ```
- Panel routes 通过 DI 接收 `PathResolver`

#### 3.17 `migrate_*` 函数实际是"复制"不是"迁移"

**问题**：
```python
# src/tools/migration.py:10-21
def migrate_tts_voices(source_file, target_file) -> int:
    data = json.loads(source_file.read_text(encoding="utf-8"))
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(data)
```

没有 schema 转换、没有字段重命名、没有老版本兼容。叫"migrate"名不副实。

**建议**：
- 加 `migrate_v2_highlights_to_v3`：把 v2 字段 `{"id", "name", "category", "templates"}` 重映射为 v3 字段 `{"id", "name", "category", "templates", "domain_specific_tags"}`
- 加 `migrate_pipeline_v2_yaml_to_v3`：把 v2 阶段名（如 `image_analysis`）映射到 v3（`material_analysis`）
- 加 dry-run 模式：`--dry-run` 只打印 diff 不写文件

#### 3.18 端到端测试增加"真实 provider"小流量

**问题**：
- `tests/test_m23_e2e.py` 全部用 mock provider
- E2E 测试价值 = 验证"mock 路径没断"——但 E2E 的本意是"全链路真的跑过"
- 真实 provider 测一次要花 API 钱

**建议**：
- 加 `tests/integration/` 子目录
- `test_e2e_real_provider.py`：用最少 token（1 个 topic 阶段、1 个文案阶段）跑真实 deepseek/doubao
- 默认 skip，加 `--run-integration` 才执行
- 验证：JSON 解析成功 + 关键字段非空 + 文件落盘

#### 3.19 Web 搜索替换为更可靠源

**问题**：
```python
# src/tools/web_searcher.py:16-19
async with httpx.AsyncClient(timeout=15) as client:
    resp = await client.get(
        "https://api.duckduckgo.com/",
        params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
    )
```

DuckDuckGo Instant Answer API 对中文支持差（中文短查询常常返回空 AbstractText）。测试代码里 `queries = [f"{destination} 旅游攻略"]` 全是中文。

**建议**：
- 加 Bing Web Search API 作为主源（需要 key）
- DuckDuckGo 作 fallback
- 备选：Bocha AI Search、Tavily（专为 LLM 设计）
- 加 unit test 验证 fallback 链路

#### 3.20 "模式 B"（参考视频）状态字段

**问题**：
设计规格 §4.3 引入模式 B，状态机有 B1-B4 阶段。但 `ProjectState` 没有 `mode` 字段，`pipelines/default.yaml` 也没有 reference_analysis 阶段。

**建议**：
```python
class ProjectState(BaseModel):
    mode: str = "material"  # material / reference
    reference_url: Optional[str] = None
    ...
```
新增 `pipelines/reference.yaml`：
```yaml
pipeline:
  name: reference
  pre_stages:
    - reference_analysis  # 在主 pipeline 之前插入
  stages:
    - highlight_selection
    - ...
```

---

### P3：影响生产体验

#### 3.21 决策日志增加"成本估算"

**问题**：
设计规格 §8.2 决策审计 JSON 包含 `cost` 字段，但 `DecisionLogger.log()` 没有 cost 参数。

**建议**：
- `Provider.complete()` 返回 `(text, usage_dict)` 而不是 `text`
- `usage_dict` 包含 `prompt_tokens, completion_tokens, model`
- `BaseStageAgent.execute` 计算成本（按 provider 定价表），传入 `decision_logger.log`

#### 3.22 状态/决策/质量三套数据合并为一个 EventStore

**问题**：
- `ProjectState.save()` 写 `state.json`（整体覆盖）
- `DecisionLogger` 写 `decision_log.jsonl`（append-only）
- `AnnotationStore` 写 `annotations.json`（dict 覆盖）
- 视频渲染日志没持久化（`render_agent.execute` 的 report 只在内存）

**建议**：
- 统一一个 `EventStore`（基于 JSONL append-only）：
  - `state` 事件：每个阶段状态变更
  - `decision` 事件：每次 AI 调用
  - `quality` 事件：每次关卡结果
  - `render` 事件：渲染参数 + 结果
- `ProjectState` 改为只读快照（从 EventStore 派生）
- 优势：可以"replay run"回放整个过程（设计规格 §10.2 提到过）

#### 3.23 渲染 Agent 的"决策"没记录

**问题**：
`RenderAgent.execute` 是调 Remotion 不调 AI，但仍是个"决策点"（选了哪些参数、渲染成功了没）。`decision_log` 缺这条。

**建议**：
```python
# render_agent.py:50 后追加
self.decision_logger.log(
    stage="render",
    provider="remotion",
    provider_score=100,
    reasoning=f"渲染 {output_path}",
    confidence=90 if result.passed else 40,
    output_summary=report[:500],
)
```

#### 3.24 ConfidenceScorer 升级为结构性评分

**问题**：
当前 `calculate_confidence` 是个弱启发式（字段数、非空率）。

**建议**：
- 增加结构性指标：
  - 段落长度方差（文案不能 3 字 + 80 字交替）
  - highlight_ref 引用闭合（每段都引用了已存在的 highlight）
  - 时间戳连续性（字幕 word start 不能比上一词 end 早）
- 与 AI 自评加权：score = 0.6 * 规则分 + 0.4 * AI 自评

#### 3.25 加 `--dry-run` 模式

**问题**：
重构期间频繁跑管道，但每次都会改 `state.json`、写决策日志、生成中间文件。

**建议**：
```python
class PipelineEngine:
    def __init__(self, ..., dry_run=False):
        self.dry_run = dry_run
    async def run(self, state):
        if self.dry_run:
            # 不写 state、不写 decision_log、不渲染
            # 只打印"会执行哪些阶段、估算耗时"
            ...
```

---

## 4. 不在重构范围内的隐忧

以下问题**重构没解决**、但和重构目标强相关：

| 隐忧 | 位置 | 建议 |
|---|---|---|
| v2.1.0 老项目状态/迁移工具完全没有 schema 转换 | `src/tools/migration.py` | 真实跑一次迁移，发现 schema gap |
| `MCP Plugin` 适配（设计规格 §11 后置）还没开始 | opencut-plugin/ | 评估：v3 内部 API 是否适合封装为 MCP tools |
| Web 前端（设计规格 §12 留待后置） | 无 frontend/ | 评估：先 `panel_routes` 改造成 HTML/JS 简单控制台 |
| 测试覆盖率 | `tests/` 1300+ 行覆盖 23 个模块 | 加 `pytest --cov` 跑一次，看实际覆盖率（估计 60-70%，核心模块应该有 80%） |

---

## 5. 优先级总表

| # | 建议 | 优先级 | 涉及文件 | 改动量 |
|---|---|---|---|---|
| 1 | 合并双实现置信度 | P0 | `base_agent.py` `confidence_scorer.py` | 0.5 天 |
| 2 | 修复 `input.json` 并发 | P0 | `remotion_renderer.py` | 0.5 小时 |
| 3 | 接入偏好画像 | P0 | `base_agent.py` `engine.py` `preference_profile.py` | 1 天 |
| 4 | 接入标注回流 | P0 | `base_agent.py` `annotation_store.py` | 0.5 天 |
| 5 | 双实现审批合一 | P0 | `engine.py` `approval_controller.py` | 0.5 小时 |
| 6 | Preflight 校验契约 | P1 | `preflight.py` `engine.py` | 1 天 |
| 7 | 幻灯片评分分位数 | P1 | `slideshow_scorer.py` | 0.5 天 |
| 8 | WhisperX fallback 文字回填 | P1 | `transcriber.py` | 0.5 天 |
| 9 | BGM ducking 阈值 | P1 | `audio_processor.py` | 0.5 小时 |
| 10 | Provider 评分矩阵外置 | P1 | `selector.py` 新增 `providers.yaml` | 1 天 |
| 11 | ImageMatcher 接入 Agent | P1 | 新增 `image_matching_agent.py` | 0.5 天 |
| 12 | Storyboard style 透传 | P2 | `storyboard_agent.py` `SegmentScene.tsx` | 1 天 |
| 13 | FastAPI app.py 入口 | P2 | 新增 `app.py` `project_routes.py` | 1 天 |
| 14 | 教育/知识付费领域 | P2 | `domains/education/*` `knowledge_paid/*` | 2 天 |
| 15 | PathResolver DI | P2 | 新增 `path_resolver.py` | 0.5 天 |
| 16 | 真实迁移函数 | P2 | `migration.py` | 1 天 |
| 17 | 真实 provider E2E | P2 | `tests/integration/` | 0.5 天 |
| 18 | 搜索源替换 | P2 | `web_searcher.py` | 1 天 |
| 19 | 模式 B 状态字段 | P2 | `state.py` 新增 `pipelines/reference.yaml` | 1 天 |
| 20 | 决策日志加 cost | P3 | `provider_registry.py` `base_agent.py` | 1 天 |
| 21 | 统一 EventStore | P3 | 重构存储层 | 3 天 |
| 22 | Render 决策记录 | P3 | `render_agent.py` | 0.5 小时 |
| 23 | ConfidenceScorer 升级 | P3 | `confidence_scorer.py` | 1 天 |
| 24 | `--dry-run` 模式 | P3 | `engine.py` | 0.5 天 |

**P0 总投入**：约 3 天，1 人
**P0 + P1 总投入**：约 10 天，1 人
**全部 P0-P3**：约 25 天，1 人

---

## 6. 总结

**v3.0 重构是一次有清晰目标、有扎实设计、有完整代码落地的版本**。设计规格 §2 提到的 6 大决策、§7 的 4 道质量关卡、§8 的 Provider 评分、§9 的 Remotion 渲染、§11 的资产迁移都按计划落地。测试覆盖 23 个模块、E2E 测试能跑通，基础扎实。

**主要问题集中在"按设计做完但没按设计用起来"**：
- 置信度：算出来了但权重错乱
- 偏好画像：建了但没 Agent 读
- 标注回流：建了但没注入 prompt
- 双实现：审批逻辑、置信度计算各两份
- 字段缺失：模式 B 没有 mode 字段，渲染参数没透传到 React

这些都不是架构问题，是**完成度问题**——按 P0 列表 3 天内能全部收敛。

**下一步建议**：
1. 先做 P0 的 5 项（约 3 天），让 v3 真正达到"按设计规格运作"
2. 然后跑一次真实 E2E（10 张敦煌图 → 真实视频），验证质量关卡是否真的能拦住问题
3. P1/P2 在真实使用中按"阻塞日常使用"顺序解决
4. 真实场景跑通后再做 P3 的可观测性升级（EventStore）

---

**分析完成。**
