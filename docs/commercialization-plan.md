# OpenCut v3 商业化方案与计划

> 制定日期：2026-07-13｜配套文档：[market-research.md](market-research.md)（市场调研与定价基准）
> 决策前提：合规移出 P0（详见调研文档第 5 节风险提示），B2C 公网上线前再补。

## 一、战略定位

**差异化**：OpenCut v3 是 **20 阶段自动化生产管道**（素材 -> 一键成片），区别于 CapCut 的编辑器中心、HeyGen 的数字人中心。主打教育/知识付费/旅行等垂直领域的「批量化、可配置、可私有化」。

**三模式落地顺序**：
1. **B2C SaaS**（引流）：免费 tier + $12-28/月中端，对标 Runway/Pika。国内因剪映免费压力，定价更低或拼垂直体验。
2. **API 授权**（开发者）：对标 HeyGen/Kling API，pay-as-you-go，20 阶段封装成「素材->成片」一条 API。
3. **私有化部署**（利润）：竞品空白点，卖给教培/政企/品牌，数据不出域，单价高（对标 Kling 企业 2000-5000 USD/月起）。

**优先切入建议**：国内 B2B 私有化部署（教培/知识付费机构）-- 合规门槛相对 B2C 低、竞品空白、单价高、领域配置（education/knowledge_paid）天然契合。B2C SaaS 作第二阶段。

## 二、架构变更（相对当前代码库）

当前：Python 管道（`src/`）+ FastAPI（`api/`）+ Remotion（`remotion/`）+ CLI（`scripts/run_full.py`）+ 本地文件系统（`data/projects/<id>/`）

目标 SaaS 架构：
```
web/            Next.js 前端（上传/选领域/预览/下载/账户/套餐）   [新增]
api/            FastAPI 扩展（认证/任务提交/计费/状态查询）        [扩展]
workers/        Celery + Redis 异步跑 20 阶段管道                  [新增]
src/            管道核心（保持，被 worker 调用）                    [不变]
remotion/       渲染层（Phase 1 上 Lambda）                        [改造]
infra/          OSS/S3 + PostgreSQL + Redis 部署配置               [新增]
```

技术选型：
- 前端：Next.js（React，与 Remotion 生态一致）
- 任务队列：Celery + Redis（Python 后端，渲染耗时几分钟必须异步）
- 对象存储：OSS（国内）/ S3（海外）存素材与产物
- 数据库：PostgreSQL（用户/项目/计费元数据；`state.json` 仍作管道运行态）
- 认证：Auth.js / Supabase Auth
- 计费：Stripe（海外）+ 微信/支付宝（国内）

## 三、分阶段计划

### Phase 0 -- MVP（让 B2C 能用、能收钱）~6 周

目标：从 CLI 工具变成「上传素材 -> 一键出片 -> 付费下载」的 web 产品，最小可验证。

> **v0.4.0 进度（2026-07-14）**：0.1/0.2/0.3/0.4/0.5/0.7/0.8 已完成（用户系统改 SQLite+JWT 非 Postgres+OAuth；异步任务用线程池非 Celery；Web UI 用 Next.js）。0.6 计费推迟到 v0.5.0（真实收款需商户号）。MVP 边界见 CLAUDE.md「SaaS 层」。

| # | 任务 | 涉及代码 | 说明 |
|---|------|---------|------|
| 0.1 | AI 生成标识渲染开关 | `remotion/src/components/` 新增 `<AiLabel>` 组件，默认关 | 1 天工作量，未来合规一键开，零返工 |
| 0.2 | Web UI 骨架 | `web/`（新） | 上传/选领域/进度条/预览/下载 |
| 0.3 | 素材支持视频直传 + 自动抽帧 | `api/` 上传接口 + ffmpeg 抽帧 worker | 当前只认 `*.jpg` 前 5 张（已知坑#5），要支持视频/png/jpeg |
| 0.4 | 异步任务层 | `workers/`（新）Celery 包装 `run_full.py` | 渲染耗时几分钟，必须异步 + 进度回传 |
| 0.5 | 用户系统 | `api/auth/` + PostgreSQL | 注册/登录/OAuth |
| 0.6 | 套餐 + 计费 | `api/billing/` + Stripe/微信支付宝 | 免费 tier（限条数）+ 1 个付费 tier |
| 0.7 | 稳定性增强 | `src/agents/base_agent.py` 等 | AI 重试指数退避（当前只重试1次）、扫 copywriter/storyboard 的 xxx_plan 风险、质量关卡阈值可配置 |
| 0.8 | API Key 平台托管 | `api/` + 密钥管理 | 用户不接触 `.env`，平台统一 key 池 |

### Phase 1 -- 运营化（能跑起来、能控成本）~6 周

| # | 任务 | 涉及代码 | 说明 |
|---|------|---------|------|
| 1.1 | Credit 计量 + 计费 | `api/billing/` + `decision_logger` | 对标 Runway credit 模型；`cost_total` 已记录，作计量基础 |
| 1.2 | 多租户隔离 + 权限 | `data/projects/` 加 user 维度 + DB 权限 | 当前仅按 project 隔离 |
| 1.3 | 监控 | Sentry + dashboard | 每阶段成功率/耗时/成本，`decisions.jsonl` 作数据源 |
| 1.4 | 模型分层 | `src/providers/selector.py` | 便宜模型跑选题/标题，强模型跑文案/素材分析（对标 HeyGen 3cr vs 20cr 分档） |
| 1.5 | 渲染上 Remotion Lambda | `remotion/` 改造 + Lambda 部署 | 多分钟视频成本几分钱，降本 |
| 1.6 | API 层补全 | `api/` 加认证/限流/计量 | 对接 API 授权模式（HeyGen/Kling 式） |
| 1.7 | 中间结果缓存 | `src/` 各 agent | 相同素材/文案段的 TTS/分析结果缓存 |

### Phase 2 -- 差异化（私有化 + 扩品类）~8 周

| # | 任务 | 说明 |
|---|------|------|
| 2.1 | 私有化部署包 | bundle + bootstrap（已有）+ 离线模型选项，卖给教培/政企（数据不出域） |
| 2.2 | 数字人 | 接 minimax 数字人或第三方，补视觉口播（HeyGen/Synthesia/CapCut 都有） |
| 2.3 | 模板市场 | 领域模板（education/travel/knowledge_paid 已有 4 个）开放给创作者上传/售卖 |
| 2.4 | 协作/团队版 | 对标 CapCut 团队版 / Runway Enterprise seats |

## 四、成本结构（per-video，待实测）

当前每条视频的模型调用成本构成（需实测填数）：
- minimax M3 多模态（素材分析，5 张图）
- minimax LLM（选题/文案/分镜等 ~10 次调用）
- minimax TTS t2a_v2（~8 段，按字符计）
- doubao（fallback，按需）
- Remotion 渲染（本地无云成本；上 Lambda 后几分钱）

**定价对标**：Runway $12-76/月 + credit 制。国内 B2C 因剪映免费，定价要更低或拼垂直体验。建议先实测 per-video 成本，再倒推 credit 单价与套餐配额（成本 × 2-3 倍加成）。

## 五、主要风险

| 风险 | 影响 | 对策 |
|------|------|------|
| 剪映免费 + 字节生态 | 国内 B2C 难打价格战 | 主攻垂直领域体验 + 私有化（剪映不做） |
| 国内合规门槛 | B2C 公网需算法备案 + AI 标识 | 先做 B2B 私有化；B2C 上线前补备案 + 开 AI 标识开关 |
| 海外 Runway/HeyGen/Pika 占位 | 获客成本高 | 海外走 API 授权（开发者）+ 垂直领域 |
| 模型 API 成本波动 | 利润不稳 | 模型分层 + 缓存 + 自建轻量模型兜底 |
| 渲染耗时长 | 用户体验差 | 异步 + 进度回传 + Remotion Lambda 并行 |

## 六、下一步

立即启动 Phase 0。建议先做的三件事（投入小、解锁大）：
1. **0.1 AI 生成标识开关**（1 天）-- 零返工未来储备
2. **0.7 稳定性增强**（2-3 天）-- 现有代码库直接改，不依赖架构变更
3. **0.3 素材支持视频直传 + png/jpeg**（2-3 天）-- 解除「只认 .jpg」的最大易用性瓶颈

Web UI / 用户系统 / 计费 / 异步任务层是重活，按 0.2 -> 0.4 -> 0.5 -> 0.6 -> 0.8 顺序推进。
