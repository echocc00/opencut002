# OpenCut Web UI（v0.4.0）

Next.js 前端，调用 FastAPI 后端（`src/api/`）。

## 开发运行

1. 先启动后端（项目根目录）：
   ```bash
   .venv/Scripts/activate          # Windows
   uvicorn src.api.app:app --reload --port 8000
   ```

2. 再启动前端（本目录）：
   ```bash
   npm install
   npm run dev
   ```
   打开 http://localhost:3000

## 工作流

1. 注册/登录（`/login`）
2. 新建项目（`/projects/new`）：上传素材图片/视频 + 选领域 -> 自动启动任务
3. 项目详情（`/projects/[id]`）：轮询 20 阶段进度，完成后下载 `final.mp4`

## 代理配置

`next.config.js` 把 `/api/*` 代理到 `http://localhost:8000`（`BACKEND_URL` env 可改）。
生产部署需改为反向代理（nginx）或同源部署。

## 管理员

管理员通过 `POST /api/admin/keys` 录入 LLM provider key（用户不接触 .env）。
可用 curl 调（需 admin token）：
```bash
curl -X POST http://localhost:8000/api/admin/keys \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"provider":"minimax","api_key":"<your-key>","model":"MiniMax M3"}'
```
