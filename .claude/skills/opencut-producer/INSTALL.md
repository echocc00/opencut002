# opencut-producer skill - 安装与分发

本文件给人看：如何把 OpenCut v3（项目 + skill + bootstrap）分发到另一台机器，
让 agent 解压即用。

## 方式一：bundle zip（推荐，自包含）

把整个项目 + skill + bootstrap 打成一个 zip，目标机器解压后跑 bootstrap 即可。

### 打包（源机器，已部署 OpenCut v3）

```bash
cd <OPENCUT_DIR>
python scripts/pack.py
# 产出 opencut-v3-3.0.0-bundle.zip（约 4 MB）
# 含：源码 + skill + bootstrap + .env.example + 文档
# 不含：依赖（.venv/node_modules）、运行时（data）、密钥（.env）
```

### 分发 + 部署（目标机器）

```bash
# 1. 解压
unzip opencut-v3-3.0.0-bundle.zip        # Windows 也可右键解压
cd opencut-v3-3.0.0/

# 2. 一键装环境（检查 Python/Node/ffmpeg，建 venv，pip install，npm install，初始化 .env）
scripts\bootstrap.bat                     # Windows
bash scripts/bootstrap.sh                 # macOS/Linux

# 3. 编辑 .env 填 MINIMAX_API_KEY 和 DOUBAO_API_KEY（bootstrap 已从 .env.example 复制）

# 4. 冒烟测试
PYTHONUTF8=1 python scripts/run_full.py   # 期望 12 阶段全 completed
```

部署后在该目录打开 Claude Code，`.claude/skills/opencut-producer/` 自动加载，
CLAUDE.md 自动加载。说"用 xxx 素材剪个视频"即触发 skill。

### 让本机所有会话可用（可选）

默认 skill 仅在项目目录内可用。要全局可用（任何会话都能触发）：

```bash
cp -r .claude/skills/opencut-producer ~/.claude/skills/
```

## 方式二：仅装 skill（项目已用 git clone 部署）

若目标机器已 clone 项目源码，只需补 skill：

```bash
cp -r <OPENCUT_DIR>/.claude/skills/opencut-producer ~/.claude/skills/
```

## bundle 内容清单

含：`src/` `domains/` `pipelines/` `scripts/` `tests/` `docs/` `config/`
`remotion/`（无 node_modules）`CLAUDE.md` `README.md` `.env.example`
`pyproject.toml` `.claude/skills/opencut-producer/` `bootstrap.bat` `bootstrap.sh` `pack.py`。

不含（需目标机器自备）：Python 3.10+、Node 18+、ffmpeg、remotion 的 npm 依赖
（bootstrap 会 `npm install`）、`.env` 真实 key（用户填）。

## 验证安装

部署后在项目目录开 Claude Code，问："用 data/projects/test/materials 的素材剪个视频"
应触发此 skill。或直接说："调用 opencut-producer"。

agent 应能：判断是否首次部署 -> 跑 bootstrap（若需）-> 检查环境 -> 准备素材 ->
跑 `run_full.py --full` -> 验收产物。

## 触发词

用户说这些时会自动调用：

- "用这些素材剪个视频"
- "根据这些图片做个解说短视频"
- "把这批视频素材剪成一条"
- "产一条竖版短视频"

## 自定义

- 改默认领域：编辑 `SKILL.md` 第 3 步
- 加排障条目：`SKILL.md` 排障速查 + `reference.md` 已知坑
- 改触发词：`SKILL.md` frontmatter 的 `description`
- 改完重新打包：`python scripts/pack.py`
