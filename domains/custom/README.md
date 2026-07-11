# 自定义领域

这是一个**自定义领域模板**，用于快速创建新的视频生产领域。

## 如何创建新领域

### 1. 复制模板

```bash
cp -r domains/custom domains/<你的领域名>
# 或从 travel 复制（更完整）：
cp -r domains/travel domains/<你的领域名>
```

### 2. 修改配置文件

| 文件 | 作用 | 必改内容 |
|------|------|---------|
| `style.yaml` | 视觉/节奏/文案/音色/BGM 风格 | `domain`、`display_name`、`copywriting.tone`、`bgm.mood` |
| `highlights.json` | 亮点归类库 | 6 条本领域常用的亮点类型 |
| `voices.json` | 可用音色 | 按领域调性选 edge-tts 音色 |
| `research.json` | 选题调研搜索词模板 | `{topic}`/`{destination}` 占位的搜索词 |
| `opening_templates.yaml` | 开场模板 | 4 种开场结构 |
| `skills/*.md` | 各阶段 prompt 指导 | 按领域调整输出要求 |

### 3. 添加 BGM

把 3-5 个本领域合适的 mp3 放入 `bgm/`。当前 `bgm/ambient.mp3` 是占位文件，请替换。

### 4. 运行

```python
state = ProjectState(project_id="xxx", domain="<你的领域名>", approval_mode="full_auto", materials=materials)
await eng.run(state)
```

## 领域完整性自检

新增领域后，确保 5 个配置文件齐全 + 15 个 skill 文件齐全 + bgm/ 至少 1 个 mp3。
可参考 `tests/test_domain_completeness.py` 的校验逻辑。
