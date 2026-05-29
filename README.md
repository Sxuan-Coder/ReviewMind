# ReviewMind

ReviewMind 是一个面向开发者的 AI PR Review 助手。当前版本完成前后端最小可运行骨架，后续按小 PR 逐步接入 GitHub PR 拉取、Diff 解析、AST 上下文和 LangGraph 多 Agent 工作流。

## 当前骨架能力

- FastAPI 后端入口
- `/api/v1/health` 健康检查
- `/api/v1/review/jobs` 创建 Review 任务占位接口
- `/api/v1/review/stream/{job_id}` SSE 进度占位接口
- `/api/v1/review/jobs/{job_id}` 报告占位接口
- React + Vite 前端首页
- PR URL 输入、任务创建、报告占位展示

## 项目结构

```text
.
├── backend/        # FastAPI 后端服务
├── frontend/       # React + Vite 前端应用
├── docs/           # 架构与设计文档
├── .github/        # PR 模板
└── docker-compose.yml
```

## 后端启动

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

健康检查：

```bash
curl http://localhost:8000/api/v1/health
```

## 前端启动

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

访问：

```text
http://localhost:5173
```

## 后续 PR 拆分建议

1. `feat: 实现 GitHub PR URL 解析与拉取`
2. `feat: 实现 DiffFilter 与 Diff Parser`
3. `feat: 实现轻量 AST Context Engine`
4. `feat: 接入 LangGraph Review Workflow`
5. `feat: 实现前端分析页和报告页`

## 第三方依赖说明

后端：FastAPI、Pydantic、Uvicorn、httpx。  
前端：React、Vite、TypeScript、TanStack Query、Zustand。
