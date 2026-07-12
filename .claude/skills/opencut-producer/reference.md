# OpenCut Producer - 深度参考

本文件是 [SKILL.md](SKILL.md) 的深度补充，供排查复杂问题时查阅。

## 20 阶段管道详解

管道定义在 `pipelines/default.yaml`。每阶段在 `data/projects/<id>/state.json` 的
`stages.<name>` 下有 `status` / `error` / `output` / `confidence_score`。

| # | 阶段 | 类型 | 作用 | 关键失败征兆 |
|---|------|------|------|-------------|
| 1 | material_analysis | auto | 用 doubao 视觉看图，输出图片描述/场景类型/目的地 | 输出描述与图无关 -> doubao 未生效 |
| 2 | web_research | auto | 搜热点/角度（`run_full.py` 里 mock 掉了，避免网络抖动） | 跳过即可，不影响出片 |
| 3 | topic | decision | 选选题方向 | 空 -> 让 LLM 重试 |
| 4 | highlight_selection | decision | 从领域 highlights 选亮点类型 | - |
| 5 | copywriting | decision | 生成 N 段文案（paragraphs） | 段落被拆碎 -> 字幕断句问题根源 |
| 6 | image_matching | auto | 文案段 -> 素材图匹配 | AI 返回不存在的文件名 -> 已有校验回退 |
| 7 | voice_selection | decision | 选音色 | - |
| 8 | tts | auto | 逐段 minimax async TTS + ffprobe 时长 + ffmpeg concat | 无声 / 时长 0 -> 看错误 |
| 9 | storyboard | decision | 段落 -> 分镜段（含转场） | AI 猜测段边界 -> 已用段落级对齐修正 |
| 10 | opening_review | quality_gate | 开场审核 | WARN 不阻断 |
| 11 | slideshow_check | quality_gate_auto | PPT 风险评分 | WARN 不阻断 |
| 12 | bgm | decision | 选 BGM + 音量 | - |
| 13 | rhythm | auto | 段落节奏 | - |
| 14 | title | decision | 选标题 | - |
| 15 | cover | decision | 选封面 | - |
| 16 | fine_cut | auto | 微调 | 默认空调整 |
| 17 | pre_render_check | quality_gate_auto | 渲染前校验（tts 音频存在等） | ERROR 阻断 |
| 18 | render | auto | Remotion 渲染 final.mp4 | npx / file:// / 时长不对 |
| 19 | post_render_check | quality_gate_auto | 渲染后校验 | ERROR 阻断 |
| 20 | deliver | manual | 标记交付 | - |

**质量关卡**：`opening_review` / `slideshow_check` 只 WARN 不阻断；
`pre_render_check` / `post_render_check` 会 ERROR 阻断，必须修。

## 已知坑详解

### 1. Windows GBK 编码

- **现象**：`UnicodeEncodeError: 'gbk' codec can't encode ...`
- **根因**：Windows 控制台默认 GBK，中文/emoji 编不出。
- **解法**：命令前加 `PYTHONUTF8=1`。`run_full.py` 已内置 `sys.stdout.reconfigure`，
  但子进程（如 ffmpeg 调用）可能仍需环境变量。
- **相关**：测试读 UTF-8 文件用 `read_text(encoding="utf-8")`。

### 2. Remotion 禁用 file://

- **现象**：渲染时图片/音频加载失败，黑帧或无声。
- **根因**：无头 Chrome 不允许 `file://` 协议。
- **解法**：`render_agent._stage_asset` 把素材拷到 `remotion/public/<project_id>/`，
  Remotion 通过相对路径访问 public。**不要在渲染数据里塞绝对路径**。
- **相关**：`remotion/public/` 下会累积项目素材，可定期清理。

### 3. TTS 用 minimax async（t2a_async_v2）

- **现象**：视频无声，或 TTS 阶段 error。
- **根因**：早期用 edge-tts（不可靠）和同步 t2a_v2（需 GroupId）。现用
  `t2a_async_v2`：创建任务 -> 轮询 `/v1/files/retrieve` -> 下载 tar -> 解 mp3。
- **解法**：确认 `MINIMAX_API_KEY` 有效。模型 `speech-2.8-hd`，voice_setting
  用 `audiobook_male_1` / `audiobook_female_1`。
- **相关**：`src/tools/tts_generator.py`、`src/agents/tts_agent.py`。
- **段落级 TTS**：每段文案单独合成，ffprobe 探精确时长，ffmpeg concat 拼接。
  TTS 是时间源，不做转写对齐（成熟做法）。

### 4. 素材分析必须用 doubao 视觉

- **现象**：素材描述与图无关（教室说成雪山）。
- **根因**：文本 LLM 看不见图，靠文件名猜。
- **解法**：`material_analysis_agent` 用 doubao 多模态（base64 image_url）。
  确认 `.env` 配了 `DOUBAO_API_KEY` 且 `DOUBAO_MODEL=doubao-seed-2-0-lite-260428`。
- **相关**：`src/agents/material_analysis_agent.py`、
  `src/providers/provider_registry.py` 的 `make_openai_provider`（处理 images kwarg）。

### 5. doubao 模型 ID 不是显示名

- **现象**：doubao 调用 404 "model does not exist"。
- **根因**：用了显示名 `Doubao-Seed-2.0-lite` 而非模型 ID。
- **解法**：`DOUBAO_MODEL=doubao-seed-2-0-lite-260428`。

### 6. 素材必须是 .jpg（取前 5 张）

- **现象**：`run_full.py` 报"0 张素材"。
- **根因**：代码 `mat_dir.glob("*.jpg")[:5]`，只认 .jpg。
- **解法**：源是视频先 `ffmpeg -i src.mp4 -vf fps=1/5 frame_%02d.jpg` 抽帧。
  挑 5-10 张不同场景的。.png 需先转 .jpg。

### 7. 字幕是整段淡入（不逐词高亮）

- **现象**：逐词高亮不可靠（转写时间戳不精确）。
- **解法**：已改为整段淡入（spring opacity + 上移）。句子-画面对齐由段落级 TTS
  保证：1 段文案 = 1 段 TTS = 1 个分镜段。
- **相关**：`remotion/src/components/WordByWordSubtitle.tsx`（组件名保留历史，
  实际是整段淡入）。

### 8. 视频时长与音频不对齐

- **现象**：视频在音频结束前结束，或最后一句没画面。
- **根因**：渲染数据用 `actualDuration`（camelCase），若读 `actual_duration`
  会 fallback 到 3.0s/段。
- **解法**：`remotion_renderer.py` 读 `actualDuration`；`render_agent` 按
  `paragraph_timing` 精确构建段时长。已修复，勿回退。

## 数据流契约速览

改 Agent 输出字段时必读 `docs/data-flow-contract.md`。要点：

- Python 侧 snake_case（`actual_duration`），Remotion 侧 camelCase（`actualDuration`）。
- 转换在 `RemotionRenderer.build_render_data()`。
- 渲染数据路径用相对项目根的相对路径，不用绝对路径。
- `copywriting.paragraphs` 是下游（image_matching / tts / storyboard）的共同源，
  改它要同步下游消费。

## 决策日志

`data/projects/<id>/decisions.jsonl` 记录每阶段的 AI 决策（prompt 摘要、输出、
token、cost）。排查"为什么选了这个"时查它。
