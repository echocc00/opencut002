# OpenCut v3.0 数据流契约表

> 每个阶段的 input_data 来源、谁注入、输出字段、下游消费者

| 阶段 | input_data 来源 | 谁注入 | 上游输出依赖 | 输出字段 | 下游消费者 |
|------|----------------|--------|-------------|---------|-----------|
| material_analysis | state.materials | project_routes | 无 | images, destination, scene_types | web_research, topic, image_matching |
| web_research | 内部生成（搜索+AI） | web_research_agent | material_analysis.destination | hot_topics, angle_suggestions, avoid_angles, differentiation | topic |
| topic | 无（用upstream_context） | - | material_analysis, web_research | directions, selected | highlight_selection, copywriting, title |
| highlight_selection | DomainConfig.highlights | engine | topic | options, selected | copywriting |
| copywriting | highlight_selection.options[selected] | engine | topic, highlight_selection | paragraphs, tone | image_matching, voice_selection, tts, storyboard, title |
| image_matching | 无（读state） | - | copywriting, material_analysis | matches | storyboard |
| voice_selection | DomainConfig.voices | engine | copywriting | candidates, selected | tts |
| tts | 无（读state） | - | copywriting, voice_selection | audio_path, word_timestamps, full_text | storyboard, render |
| storyboard | 无（用upstream_context） | - | copywriting, image_matching, tts | segments, total_duration | opening_review, slideshow_check, bgm, rhythm, cover, fine_cut, render |
| opening_review | 无（读state） | - | storyboard | passed, checks | (质量关卡) |
| slideshow_check | 无（读state） | - | storyboard, topic | total_score, risk_level, passed, suggestions | (质量关卡) |
| bgm | domains/{domain}/bgm/ 目录 | engine | storyboard | candidates, selected_path, volume | rhythm, render |
| rhythm | 无（用upstream_context） | - | storyboard, bgm | segment_timings, bgm_start_offset | fine_cut |
| title | 无（用upstream_context） | - | copywriting | titles, selected | render |
| cover | 无（用upstream_context） | - | storyboard | cover_candidates, selected | (交付) |
| fine_cut | 无（用upstream_context） | - | storyboard, rhythm | adjustments | pre_render_check |
| pre_render_check | 无（读state） | - | fine_cut | passed, issues | (质量关卡) |
| render | 无（读state） | - | storyboard, tts, bgm, title | video_path, duration, quality_report | post_render_check, deliver |
| post_render_check | 无（读state） | - | render | passed, issues, report | (质量关卡) |
| deliver | 无（读state） | - | post_render_check | video_path, delivered | (终态) |

## 数据转换职责

| 数据 | 生产者 | 消费者 | 转换职责 | 谁负责 |
|------|--------|--------|---------|--------|
| word_timestamps | tts (全局时间轴) | render (段内时间轴) | 按segment时间段切分，转换为段内相对时间 | RenderAgent._merge_word_timestamps |
| confirmed_highlights | highlight_selection (options[selected]) | copywriting (input_data) | 从options中提取选中方案 | engine.run() |
| matches | image_matching (paragraph_index->file) | storyboard (upstream_context) | 直接传递，AI在prompt中读取 | upstream_context |
| highlights | DomainConfig.get_highlights() | highlight_selection (input_data) | 从领域配置加载 | engine.run() |
| available_voices | DomainConfig.get_voices() | voice_selection (input_data) | 从领域配置加载 | engine.run() |
| available_bgm | domains/{domain}/bgm/ 目录 | bgm (input_data) | 扫描BGM目录 | engine.run() |
| materials | project_routes (UploadFile) | material_analysis (input_data) | 从HTTP上传保存 | project_routes |

## Python -> Remotion 跨语言数据契约

### 字段名映射表

| Python 字段名 (snake_case) | TypeScript 字段名 (camelCase) | 转换位置 |
|---------------------------|------------------------------|---------|
| actual_duration | actualDuration | render_data 构建时转换 |
| time_start | timeStart | render_data 构建时转换 |
| subtitle_words | subtitleWords | render_data 构建时转换 |
| voice_path | voicePath | build_render_data 参数 |
| bgm_path | bgmPath | build_render_data 参数 |
| bgm_volume | bgmVolume | build_render_data 参数 |
| title_duration | titleDuration | build_render_data 参数 |
| cover_image | coverImage | render_data 构建时设置 |
| ai_label | aiLabel | build_render_data 参数（bool，默认 false，由 OPENCUT_AI_LABEL 环境变量控制） |

### subtitleWords 子字段

| Python 字段名 | TypeScript 字段名 | 说明 |
|--------------|------------------|------|
| word | word | 词文本 |
| start | start | 开始时间（秒，段内相对时间） |
| end | end | 结束时间（秒，段内相对时间） |

### 转换规则

1. Python Agent 输出使用 snake_case（Python 惯例）
2. `RemotionRenderer.build_render_data()` 负责将 snake_case 转为 camelCase
3. input.json 中所有字段名必须是 camelCase
4. VideoComposition.tsx 只读取 camelCase 字段

## 路径格式标准

### 规则

1. input.json 中所有路径使用**相对于项目根目录**的相对路径（不带 `../`）
2. 示例：`data/projects/edu_test/materials/img_01.jpg`
3. render_video.mjs 的 `resolvePath()` 负责将相对路径转为绝对路径（自动加 `../` 从 remotion 目录回到项目根目录）
4. Python 侧不输出绝对路径，只输出相对路径

## Remotion 约束文档

### Chrome 安全约束
- Remotion 使用无头 Chrome 渲染每一帧
- Chrome 禁止 `file://` 协议加载本地资源
- **解决方案**：render_video.mjs 将图片和音频转为 base64 data URL 后传入

### interpolate() 约束
- 输入范围必须严格递增（`inputRange[0] < inputRange[1] < ...`）
- 短词（< 12 帧 = 0.4 秒）需要特殊处理：缩小过渡帧数或跳过缩放
- 不支持颜色字符串插值（`#FF0000` -> `#00FF00` 会报错）
- **解决方案**：颜色用 CSS transition 替代，缩放用安全的插值点

### spring() 约束
- `config.damping`：阻尼，越大弹跳越少（建议 12-15）
- `config.stiffness`：刚度，越大弹得越快（建议 80-100）
- `config.mass`：质量，越大动得越慢（建议 0.8-1.0）

### 环境约束
- Remotion 安装需要本地 Node.js 环境（npm install）
- 沙箱环境（45 秒超时 + 文件权限限制）不适合安装 Remotion
- **实施计划标注**：Remotion 安装和渲染步骤必须由用户在本地执行
