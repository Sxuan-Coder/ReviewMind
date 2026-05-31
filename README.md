# ReviewMind

ReviewMind 是一个面向开发者的 AI PR Review 助手。用户只需输入 GitHub Pull Request 链接，系统即可自动拉取 PR 变更内容，通过 Diff 解析、轻量 AST 方法级上下文提取、多 Agent 协同审查与风险仲裁，最终生成结构化 Review 报告和可复制的 GitHub Review Comment。

## 当前能力

- GitHub PR URL 输入与自动解析
- PR 信息拉取（标题、作者、变更文件、Diff）
- DiffFilter 降噪过滤（lock 文件、构建产物、静态资源）
- Diff Parser 变更行解析
- 轻量 AST 方法级上下文提取（支持 Python / JS / TS / Java）
- LangGraph 多 Agent Review 工作流（Summary / Security / Performance / Test / Risk Judge / Report）
- SSE 实时分析进度推送
- 结构化 Review 报告（风险总览、风险详情、Diff 行级定位）
- 可复制 GitHub Review Comment
- 暗色主题前端界面

## Demo

🎬 **演示视频**：[ReviewMind（心流）— AI 驱动的 PR Review 助手](https://www.bilibili.com/video/BV1yqVU6EERf?vd_source=a14af81dbe58d331448421f880c825c2)



https://github.com/user-attachments/assets/aeb74279-0767-4173-8caa-71fa41da0d45





演示内容：输入 GitHub PR URL → 实时展示 Agent 分析进度 → 查看结构化 Review 报告 → 风险定位与 Diff 跳转 → 一键复制 Review Comment

## 项目结构

```text
.
├── backend/        # FastAPI 后端服务
├── frontend/       # React + Vite 前端应用
├── docs/           # 架构与设计文档
├── .github/        # PR 模板
└── docker-compose.yml
```

## 环境要求

- Python 3.12+
- Node.js 22+
- Git
- 操作系统：Windows / macOS / Linux

## 后端启动

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env      # macOS/Linux
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
copy .env.example .env   # Windows
# cp .env.example .env      # macOS/Linux
npm run dev
```

访问：

```text
http://localhost:5173
```

## Docker Compose 启动

### 方式一：使用预构建镜像（推荐）

```bash
# 1. 复制并配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env 填入你的 GITHUB_TOKEN 等配置

# 2. 启动服务
docker-compose up -d
```

首次启动后，可通过以下命令更新到最新镜像：

```bash
docker-compose pull && docker-compose up -d
```

### 方式二：本地构建

```bash
docker-compose up --build -d
```

### 服务地址

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:80 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |

### 环境变量配置

可通过 `backend/.env` 文件或环境变量覆盖默认配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `POSTGRES_DB` | reviewmind | 数据库名 |
| `POSTGRES_PORT` | 5432 | PostgreSQL 端口 |
| `BACKEND_PORT` | 8000 | 后端 API 端口 |
| `FRONTEND_PORT` | 80 | 前端访问端口 |
| `REDIS_PASSWORD` | (空) | Redis 密码 |

## 原创性声明

本项目核心功能均由本人独立设计与实现，包括：

- GitHub PR 拉取与 Diff 解析流程
- DiffFilter 降噪策略
- 轻量 AST 方法级上下文提取（支持 Python / JS / TS / Java）
- 基于 LangGraph 的多 Agent Review 工作流
- 多维度专项 Agent Prompt 设计（安全 / 性能 / 测试）
- Risk Judge 风险仲裁与置信度机制
- 结构化 Review 报告生成
- 前端 Agent 进度时间线与 Diff 行级定位交互

本项目开发过程中使用 AI 工具辅助进行代码审查、Bug 排查和文档润色。
项目核心架构设计、功能实现和测试验证均由本人完成。

### 第三方依赖声明

**后端依赖（Python）：**

| 依赖 | 用途 |
|------|------|
| FastAPI | Web 框架，提供 REST API |
| Pydantic / pydantic-settings | 数据校验与配置管理 |
| Uvicorn | ASGI 服务器 |
| httpx | 异步 HTTP 客户端，调用 GitHub API |
| LangGraph | 多 Agent Review 工作流编排引擎 |
| SQLAlchemy | ORM 与数据库访问层 |
| aiosqlite | 异步 SQLite 驱动（开发 / 轻量部署） |
| asyncpg | 异步 PostgreSQL 驱动（生产部署） |
| pgvector | PostgreSQL 向量相似度检索 |
| Redis | 缓存与异步消息队列 |
| python-dotenv | 环境变量加载 |
| pytest / pytest-asyncio | 测试框架 |

**前端依赖（TypeScript）：**

| 依赖 | 用途 |
|------|------|
| React 19 | UI 框架 |
| React Router DOM 7 | 客户端路由 |
| Vite 6 | 构建工具与开发服务器 |
| TypeScript | 类型系统 |
| TanStack React Query 5 | 服务端状态管理 |
| Zustand 5 | 客户端状态管理 |
| Tailwind CSS 4 | 样式框架 |
| shadcn / Radix UI | UI 组件库 |
| Framer Motion | 动画库 |
| Lucide React | 图标库 |
