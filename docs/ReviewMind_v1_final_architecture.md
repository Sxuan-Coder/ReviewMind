# ReviewMind v1.0 最终方案文档

> 基于轻量 AST 上下文增强与 LangGraph 多 Agent 工作流的 AI PR Review 助手

---

## 1. 项目定位

ReviewMind 是一个面向开发者的 AI PR Review 助手。用户只需输入 GitHub Pull Request 链接，系统即可自动拉取 PR 变更内容，通过 Diff 解析、轻量 AST 方法级上下文提取、多 Agent 协同审查与风险仲裁，最终生成结构化 Review 报告和可复制的 GitHub Review Comment。

本项目的核心目标不是做一个“套壳 ChatGPT 的代码问答工具”，而是实现一个能够理解 PR 变更上下文、辅助开发者发现风险、提升代码审查效率的工程化 AI Review 系统。

---

## 2. 一句话介绍

用户输入 GitHub PR 链接，系统自动拉取 Diff，通过 DiffFilter 降噪、AST 定位变更方法、LangGraph 编排多 Agent 审查，并以 SSE 实时推送分析进度和风险发现，最终生成结构化 Review 报告与可复制的 GitHub 评论。

---

## 3. 解决的核心问题

### 3.1 PR Review 效率低

开发者在面对大型 PR 时，往往需要花费大量时间理解本次改动的业务意图、影响范围和潜在风险。

ReviewMind 通过 PR 摘要、变更方法识别和风险聚合，帮助 Reviewer 快速理解 PR。

### 3.2 只看 Diff 容易误判

传统 AI Review 工具如果只分析 Git Diff 文本，很容易因为上下文缺失产生误报或漏报。

ReviewMind 在 MVP 阶段引入轻量 AST 上下文增强，将变更行定位到具体类、函数或方法，并提取方法级上下文提供给 Agent。

### 3.3 AI Review 容易泛泛而谈

单一 Prompt 容易输出笼统建议，缺少结构化风险定位。

ReviewMind 使用多 Agent 分工，从摘要、安全、性能、测试等角度分别审查，再由 Risk Judge 统一去重、评分和降噪。

### 3.4 结果难以用于真实 Review

普通 AI 输出往往是一大段文本，无法直接用于 GitHub PR 讨论。

ReviewMind 输出文件位置、代码行号、风险等级、置信度、原因、建议和可复制 Review Comment，便于开发者直接使用。

---

## 4. 最终 MVP 形态

MVP 不追求“大而全”的 DevOps 平台，而是优先跑通一个完整闭环：

```text
输入 GitHub PR URL
    ↓
创建 Review Job
    ↓
拉取 PR 基本信息和 Diff
    ↓
过滤无效 Diff
    ↓
AST 定位变更方法
    ↓
多 Agent 分析
    ↓
Risk Judge 风险仲裁
    ↓
生成结构化 Review 报告
    ↓
前端展示 + 复制 Review Comment
```

最终用户看到的是一个 Web 应用：

1. 首页输入 PR 链接。
2. 分析页实时展示 Agent 执行进度。
3. 报告页展示 PR 摘要、风险总览、风险详情、Diff 定位和可复制评论。

---

## 5. 技术栈选型

### 5.1 前端技术栈

| 模块          | 技术                        |
| ------------- | --------------------------- |
| 前端框架      | React + TypeScript + Vite   |
| 样式          | Tailwind CSS                |
| UI 组件       | shadcn/ui                   |
| 视觉增强      | Cult UI                     |
| 状态管理      | Zustand                     |
| 请求管理      | TanStack Query              |
| Diff 展示     | react-diff-viewer-continued |
| 动效          | Framer Motion，可选         |
| 代码编辑/展示 | Monaco Editor，可选         |

前端重点不是复杂后台，而是做出强演示效果：

- PR URL 输入台
- Agent 分析时间线
- 风险卡片
- Diff 行级定位
- Review Comment 复制按钮

---

### 5.2 后端技术栈

| 模块            | 技术                  |
| --------------- | --------------------- |
| 后端框架        | FastAPI               |
| 数据校验        | Pydantic v2           |
| HTTP 客户端     | httpx                 |
| AI 编排         | LangChain             |
| 多 Agent 工作流 | LangGraph             |
| AST 解析        | tree-sitter           |
| ORM             | SQLAlchemy / SQLModel |
| 数据库          | PostgreSQL            |
| 缓存            | Redis，可选           |
| 部署            | Docker Compose        |

FastAPI 负责对外 API，LangGraph 负责编排 Review 工作流，LangChain 负责 Prompt、模型调用和结构化输出。

---

### 5.3 AI 与模型

| 场景      | 推荐                                    |
| --------- | --------------------------------------- |
| PR 摘要   | DeepSeek / Qwen 小模型                  |
| 风险分析  | DeepSeek / Qwen / OpenAI-compatible API |
| 最终报告  | DeepSeek / Qwen                         |
| Embedding | bge-m3，可选                            |
| RAG       | MVP 暂不强依赖，Phase 2 接入 pgvector   |

MVP 阶段不建议强依赖 Pinecone、Milvus 等外部向量数据库。可以先通过 AST 方法级上下文增强解决主要问题，后续再接入 pgvector 做代码库级 RAG。

---

## 6. 系统总体架构

```text
GitHub PR URL
    ↓
FastAPI Review API
    ↓
Create Review Job
    ↓
SSE Stream
    ↓
LangGraph Review Workflow
    ↓
┌────────────────────────────┐
│ 1. Fetch PR Node            │ 拉取 PR 信息、files、diff
│ 2. Diff Filter Node         │ 过滤 lock/dist/大文件
│ 3. Diff Parser Node         │ 解析新增/删除/变更行
│ 4. AST Context Node         │ 定位类/函数/方法
│ 5. Summary Agent Node       │ 总结 PR 意图
│ 6. Security Agent Node      │ 安全风险
│ 7. Performance Agent Node   │ 性能风险
│ 8. Test Agent Node          │ 测试缺失
│ 9. Risk Judge Node          │ 合并、去重、评分
│ 10. Report Agent Node       │ 生成最终报告
└────────────────────────────┘
    ↓
PostgreSQL 保存任务和报告
    ↓
React 前端展示
```

---

## 7. 核心模块设计

### 7.1 GitHub PR 获取模块

负责根据用户输入的 PR URL 解析：

- owner
- repo
- pull number

然后通过 GitHub API 获取：

- PR 标题
- PR 作者
- base 分支
- head 分支
- changed files
- additions / deletions
- patch diff

MVP 阶段可以只支持公开仓库。

---

### 7.2 DiffFilter 降噪模块

DiffFilter 用于过滤不适合送入模型的文件，避免 Token 爆炸和无效分析。

默认过滤：

```text
package-lock.json
pnpm-lock.yaml
yarn.lock
dist/
build/
*.min.js
*.min.css
*.svg
*.png
*.jpg
*.jpeg
*.gif
*.ico
```

如果 PR 变更行数过大，则进行分片处理，只保留核心源代码文件。

---

### 7.3 Diff Parser 模块

Diff Parser 负责将 GitHub patch 转换为结构化数据：

```json
{
  "file": "src/services/order_service.py",
  "status": "modified",
  "additions": 12,
  "deletions": 4,
  "changed_lines": [18, 19, 20, 45],
  "hunks": []
}
```

它为后续 AST 定位和风险报告行号展示提供基础数据。

---

### 7.4 轻量 AST Context Engine

MVP 阶段的 AST 不做完整 Code Graph，而是专注于方法级定位。

核心能力：

1. 根据文件后缀选择 parser。
2. 解析类名、函数名、方法名。
3. 根据 diff 行号定位所属函数/方法。
4. 提取该方法完整代码作为上下文。
5. 输出方法签名、起止行、变更行和代码片段。

示例输出：

```json
{
  "file": "src/services/order_service.py",
  "symbol": "OrderService.create_order",
  "start_line": 32,
  "end_line": 78,
  "changed_lines": [45, 46],
  "language": "python",
  "code": "def create_order(...): ..."
}
```

AST 的价值是让 Agent 不只是看到孤立 Diff，而是知道变更发生在哪个函数、哪个类、哪个业务方法里。

---

## 8. LangGraph 多 Agent 工作流

ReviewMind 的核心不是单次 LLM 调用，而是一个多节点的 LangGraph 工作流。

```text
START
  ↓
fetch_pr
  ↓
diff_filter
  ↓
parse_diff
  ↓
ast_context
  ↓
summary_agent
  ↓
security_agent
  ↓
performance_agent
  ↓
test_agent
  ↓
risk_judge
  ↓
report_agent
  ↓
END
```

---

## 9. Agent 职责设计

### 9.1 Summary Agent

负责总结 PR 的业务意图和影响范围。

输出内容：

- 本次 PR 做了什么
- 涉及哪些模块
- 修改了哪些核心方法
- 是否属于新增功能、Bug 修复、重构或配置变更

示例：

```text
本次 PR 主要新增订单创建流程，涉及 OrderService.create_order 与 OrderRepository.save_order。
主要影响订单创建、库存校验和支付初始化逻辑。
```

---

### 9.2 Security Agent

负责识别安全风险。

重点关注：

- SQL 注入
- XSS
- SSRF
- 权限绕过
- 敏感信息泄露
- Token 泄露
- 文件上传风险
- 不安全反序列化

输出结构：

```json
{
  "type": "SQL_INJECTION",
  "level": "HIGH",
  "confidence": 0.92,
  "file": "src/mapper/order_mapper.xml",
  "line": 18,
  "reason": "使用 ${userId} 进行 SQL 字符串拼接",
  "suggestion": "改为 #{userId} 参数绑定"
}
```

---

### 9.3 Performance Agent

负责识别性能风险。

重点关注：

- 循环中查数据库
- N+1 查询
- 重复远程调用
- Redis 未设置过期时间
- 缓存击穿风险
- 长事务
- 不合理分页
- 大对象循环构建

示例问题：

```text
OrderService.create_order 中存在循环内数据库查询，数据量变大后可能造成 N+1 查询问题。
建议改为批量查询。
```

---

### 9.4 Test Agent

负责识别测试缺失和测试建议。

重点关注：

- 新增核心逻辑是否有测试
- Bug 修复是否有回归测试
- 异常路径是否覆盖
- 边界条件是否覆盖
- 是否修改测试文件

示例输出：

```text
本次 PR 新增订单创建逻辑，但未发现对应测试文件变更。
建议补充正常创建订单、库存不足、重复提交、支付失败回滚等测试场景。
```

---

### 9.5 Risk Judge Agent

负责合并多个 Agent 的输出，进行去重、降噪和评分。

职责：

1. 合并重复问题。
2. 判断是否误报。
3. 统一风险等级。
4. 给出置信度。
5. 生成最终风险列表。

风险等级：

| 等级       | 含义                                   |
| ---------- | -------------------------------------- |
| CRITICAL   | 可能导致严重安全、数据或系统稳定性问题 |
| HIGH       | 高概率影响生产质量，需要优先修复       |
| MEDIUM     | 有明确风险，但影响范围可控             |
| LOW        | 代码质量或可维护性建议                 |
| SUGGESTION | 非阻塞优化建议                         |

---

### 9.6 Report Agent

负责生成最终 Review 报告。

报告包括：

1. PR 摘要
2. 影响范围
3. 风险总览
4. 高风险问题
5. 中低风险建议
6. 测试建议
7. 可复制 GitHub Review Comment

---

## 10. API 设计

### 10.1 创建 Review 任务

```http
POST /api/v1/review/jobs
```

请求体：

```json
{
  "pr_url": "https://github.com/owner/repo/pull/101",
  "config": {
    "enable_ast": true,
    "enable_rag": false,
    "strict_mode": true
  }
}
```

响应：

```json
{
  "job_id": "rev_8f9a2b1c",
  "status": "pending",
  "stream_url": "/api/v1/review/stream/rev_8f9a2b1c"
}
```

---

### 10.2 SSE 流式接口

```http
GET /api/v1/review/stream/{job_id}
```

事件类型：

| Event    | 用途           |
| -------- | -------------- |
| progress | 推送分析进度   |
| chunk    | 推送摘要文本流 |
| finding  | 推送具体风险   |
| warning  | 推送非致命异常 |
| done     | 标记任务完成   |

示例：

```text
event: progress
data: {"step":"AST_CONTEXT","percent":35,"message":"正在定位变更方法"}
```

```text
event: finding
data: {
  "agent": "SecurityAgent",
  "file": "src/mapper/order_mapper.xml",
  "line": 18,
  "method": "selectOrderByUserId",
  "level": "HIGH",
  "type": "SQL_INJECTION",
  "confidence": 0.92,
  "description": "使用 ${userId} 拼接 SQL，存在注入风险",
  "suggestion": "改为 #{userId} 参数绑定"
}
```

---

### 10.3 获取报告详情

```http
GET /api/v1/review/jobs/{job_id}
```

返回完整 Review 报告，用于刷新页面或查看历史记录。

---

## 11. 前端页面设计

### 11.1 首页

核心目标：快速输入 PR URL。

页面内容：

```text
ReviewMind
基于多 Agent 与 AST 上下文增强的 AI PR Review 助手

[ GitHub PR URL 输入框 ]
[ 开始分析按钮 ]
```

可使用 Cult UI 做 Hero 区，提高第一眼观感。

---

### 11.2 分析页

核心目标：展示系统正在分析，而不是等待黑盒结果。

页面内容：

- PR 基本信息卡片
- Agent 执行时间线
- SSE 实时进度
- 当前发现风险列表
- 分析耗时
- Token 消耗，可选

示例：

```text
✓ Fetch PR
✓ Diff Filter
✓ AST Context
⏳ Security Agent
○ Performance Agent
○ Test Agent
○ Risk Judge
```

---

### 11.3 报告页

核心目标：让 Review 结果可读、可定位、可使用。

页面区域：

1. PR 摘要
2. 风险总览卡片
3. 变更文件列表
4. 变更方法列表
5. 风险详情卡片
6. Diff 视图
7. 可复制 Review Comment

交互重点：

- 点击风险卡片，Diff 自动滚动到对应行。
- 高亮风险代码行。
- 一键复制 GitHub Review Comment。

---

## 12. Review 报告结构

最终报告建议采用结构化 JSON 存储，前端再渲染。

```json
{
  "summary": "本次 PR 新增订单创建逻辑，并调整库存校验流程。",
  "risk_level": "MEDIUM",
  "stats": {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "suggestion": 2
  },
  "changed_symbols": [
    {
      "file": "src/services/order_service.py",
      "symbol": "OrderService.create_order",
      "start_line": 32,
      "end_line": 78
    }
  ],
  "findings": [
    {
      "type": "N_PLUS_ONE_QUERY",
      "level": "MEDIUM",
      "confidence": 0.86,
      "file": "src/services/order_service.py",
      "line": 45,
      "symbol": "OrderService.create_order",
      "description": "循环中多次访问数据库，可能造成 N+1 查询问题。",
      "suggestion": "改为批量查询。",
      "agent": "PerformanceAgent"
    }
  ],
  "review_comment": "## AI Review Summary\n\n..."
}
```

---

## 13. 项目目录结构

```text
reviewmind/
├── .github/
│   ├── workflows/
│   └── PULL_REQUEST_TEMPLATE.md
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── review.py
│   │   │   └── health.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── llm.py
│   │   │   └── database.py
│   │   ├── services/
│   │   │   ├── github_service.py
│   │   │   ├── diff_filter.py
│   │   │   ├── diff_parser.py
│   │   │   ├── ast_service.py
│   │   │   └── report_service.py
│   │   ├── agents/
│   │   │   ├── summary_agent.py
│   │   │   ├── security_agent.py
│   │   │   ├── performance_agent.py
│   │   │   ├── test_agent.py
│   │   │   ├── risk_judge_agent.py
│   │   │   └── report_agent.py
│   │   ├── graph/
│   │   │   └── review_graph.py
│   │   ├── models/
│   │   │   ├── review_job.py
│   │   │   ├── pr_file.py
│   │   │   ├── finding.py
│   │   │   └── review_report.py
│   │   ├── schemas/
│   │   │   ├── review_schema.py
│   │   │   └── report_schema.py
│   │   └── main.py
│   ├── tests/
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── review/
│   │   │   ├── diff/
│   │   │   └── report/
│   │   ├── hooks/
│   │   │   └── useReviewStream.ts
│   │   ├── services/
│   │   ├── store/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   └── .env.example
│
├── docs/
│   ├── architecture.md
│   ├── agent-design.md
│   └── roadmap.md
│
├── docker-compose.yml
├── README.md
└── .gitignore
```

---

## 14. MVP 必做功能清单

| 功能                    | 优先级  |
| ----------------------- | ------- |
| 输入 GitHub PR URL      | P0      |
| 拉取 PR 信息与 Diff     | P0      |
| DiffFilter 过滤无效文件 | P0      |
| Diff Parser 解析变更行  | P0      |
| AST 定位变更方法        | P0      |
| Summary Agent           | P0      |
| Security Agent          | P0      |
| Performance Agent       | P0      |
| Test Agent              | P0      |
| Risk Judge              | P0      |
| Report Agent            | P0      |
| SSE 实时进度            | P0      |
| 报告页风险展示          | P0      |
| Diff 行级定位           | P1      |
| 复制 Review Comment     | P1      |
| 历史报告列表            | P2      |
| Redis 缓存              | P2      |
| pgvector RAG            | Phase 2 |
| GitHub App 自动评论     | Phase 3 |

---

## 15. MVP 暂不做内容

为了保证交付质量，以下内容不进入 v1.0 MVP：

- GitHub OAuth 登录
- GitHub App 自动安装
- 自动评论 PR
- 自动 Request Changes
- 全仓库 Code Graph
- 完整跨文件调用链
- 企业权限系统
- 多租户
- OpenTelemetry 全链路追踪
- Pinecone / Milvus 强依赖
- Kubernetes 部署
- 多模型自动降级

这些内容可作为后续 Roadmap 展示，而不是第一版交付目标。

---

## 16. 误报与漏报控制策略

ReviewMind 采用三层策略降低误报：

### 16.1 DiffFilter 降噪

先过滤无意义文件，避免模型分析 lock 文件、构建产物和静态资源。

### 16.2 AST 方法级上下文

不只把单行 Diff 交给模型，而是提供所属函数、方法签名、完整方法代码和变更行。

### 16.3 Risk Judge 仲裁

多个 Agent 的输出不会直接展示给用户，而是先经过 Risk Judge：

- 合并重复问题
- 降低低置信度结果
- 将非阻塞问题标记为 SUGGESTION
- 统一风险等级
- 输出最终置信度

---

## 17. 模型选择说明

MVP 阶段采用 OpenAI-compatible API 适配层，便于切换 DeepSeek、Qwen 或其他模型。

设计原则：

1. 摘要任务使用速度快、成本低的模型。
2. 安全与性能分析使用推理能力更强的模型。
3. 报告生成使用稳定输出能力强的模型。
4. 所有 Agent 输出尽量采用结构化 JSON，降低前端解析难度。
5. Embedding 和 RAG 不作为 MVP 强依赖，避免复杂度过高。

---

## 18. 后续演进路线

### Phase 1：MVP 闭环

目标：完成可演示的 PR Review 全流程。

包含：

- FastAPI 后端
- React 前端
- GitHub PR 拉取
- DiffFilter
- 轻量 AST Context
- LangGraph 多 Agent
- SSE 实时进度
- 结构化报告
- 复制 Review Comment

---

### Phase 2：RAG 与团队规范

目标：提升上下文理解和团队适配能力。

包含：

- pgvector 代码库级 RAG
- 团队规范知识库
- 历史 Review Memory
- 相似问题检索
- 自定义规则配置
- Architecture Agent

---

### Phase 3：自动化 DevOps 闭环

目标：从 Review 助手升级为智能质量守门员。

包含：

- GitHub App
- Webhook 自动触发
- 自动评论 PR
- CRITICAL 风险自动 Request Changes
- CI/CD 集成
- OpenTelemetry 观测
- 多项目管理

---

## 19. 开发与提交策略

根据规则，需要持续交付，不能最后一天突击提交。

推荐 PR 拆分：

```text
PR #1: 初始化前后端项目结构
PR #2: 实现 GitHub PR URL 解析与 API 拉取
PR #3: 实现 DiffFilter 与 Diff Parser
PR #4: 实现轻量 AST Context Engine
PR #5: 接入 LangChain 与基础 LLM 调用
PR #6: 实现 LangGraph Review Workflow
PR #7: 实现 Summary Agent
PR #8: 实现 Security Agent
PR #9: 实现 Performance Agent
PR #10: 实现 Test Agent
PR #11: 实现 Risk Judge 与 Report Agent
PR #12: 实现 SSE 实时进度推送
PR #13: 实现前端首页与分析页
PR #14: 实现报告页与 Diff 定位
PR #15: 完善 README、架构文档与 Demo 脚本
```

每个 PR 描述应包含：

```text
本次变更：
1. 新增 xxx
2. 修改 xxx
3. 修复 xxx

测试方式：
1. 使用 xxx PR URL 测试
2. 接口返回正常
3. 页面展示正常
```

---

## 20. 第三方依赖与原创说明

README 中应明确列出第三方依赖：

- React
- Vite
- Tailwind CSS
- shadcn/ui
- Cult UI
- FastAPI
- LangChain
- LangGraph
- tree-sitter
- PostgreSQL
- Redis
- GitHub API
- DeepSeek / Qwen / OpenAI-compatible API

同时说明原创部分：

```text
本项目核心原创功能包括：
1. GitHub PR 拉取与 Diff 解析流程
2. DiffFilter 降噪策略
3. 轻量 AST 方法级上下文提取
4. 基于 LangGraph 的多 Agent Review 工作流
5. Security / Performance / Test 等专项 Agent Prompt 设计
6. Risk Judge 风险仲裁与置信度机制
7. 结构化 Review 报告生成
8. 前端 Agent 进度展示与 Diff 行级定位交互
```

如果开发过程中使用 AI 工具辅助，应在 README 中透明说明：

```text
本项目开发过程中使用 AI 工具辅助进行代码审查、Bug 排查、文档润色和测试用例建议。
项目核心功能，包括 GitHub PR 拉取、Diff 解析、AST 上下文提取、多 Agent 调度、风险规则设计、Review 报告生成等，均由本人独立设计与实现。
```

---

## 21. 最终结论

ReviewMind v1.0 的最佳策略是：

```text
不要做大而全的平台，
而是做一个小而完整、技术亮点清晰、Demo 效果强的 AI PR Review 闭环。
```

最终核心亮点：

1. GitHub PR Diff 自动拉取。
2. DiffFilter 防 Token 爆炸。
3. 轻量 AST 方法级上下文增强。
4. LangGraph 多 Agent Review 工作流。
5. Security / Performance / Test 专项审查。
6. Risk Judge 风险仲裁与误报控制。
7. SSE 实时分析进度。
8. 结构化 Review 报告与可复制评论。
