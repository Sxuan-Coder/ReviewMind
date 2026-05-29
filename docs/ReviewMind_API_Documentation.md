# ReviewMind v1.0 API 接口文档

> 基于 FastAPI 的 AI PR Review 后端接口规范  
> 适用版本：ReviewMind v1.0 MVP

---

## 1. 基础说明

### 1.1 API Base URL

本地开发环境：

```http
http://localhost:8000
```

接口统一前缀：

```http
/api/v1
```

---

### 1.2 数据格式

普通请求与响应：

```http
Content-Type: application/json
```

SSE 流式接口：

```http
Content-Type: text/event-stream
```

---

### 1.3 通用响应格式

```json
{
  "code": 20000,
  "message": "success",
  "data": {}
}
```

| 字段    | 类型                  | 说明       |
| ------- | --------------------- | ---------- |
| code    | number                | 业务状态码 |
| message | string                | 响应消息   |
| data    | object / array / null | 响应数据   |

---

### 1.4 通用错误响应

```json
{
  "code": 40001,
  "message": "Invalid GitHub PR URL",
  "data": null
}
```

---

## 2. 状态码约定

| code  | HTTP 状态码 | 含义                  |
| ----- | ----------: | --------------------- |
| 20000 |         200 | 请求成功              |
| 20200 |         202 | 任务已创建            |
| 40000 |         400 | 请求参数错误          |
| 40001 |         400 | PR URL 非法           |
| 40002 |         400 | 不支持的仓库或 PR     |
| 40100 |         401 | GitHub Token 无效     |
| 40300 |         403 | GitHub API Rate Limit |
| 40400 |         404 | 资源不存在            |
| 40900 |         409 | 任务状态冲突          |
| 42200 |         422 | 请求体验证失败        |
| 50000 |         500 | 服务内部错误          |
| 50200 |         502 | LLM 服务调用失败      |
| 50300 |         503 | Review 任务暂不可用   |

---

## 3. 健康检查接口

### 3.1 获取服务状态

```http
GET /api/v1/health
```

#### 响应示例

```json
{
  "code": 20000,
  "message": "success",
  "data": {
    "status": "ok",
    "service": "reviewmind-api",
    "version": "1.0.0"
  }
}
```

---

## 4. Review Job 接口

Review Job 是一次 PR 分析任务。

核心流程：

```text
创建 Review Job
    ↓
建立 SSE 连接
    ↓
接收 progress / finding / chunk / done 事件
    ↓
查询最终报告
```

---

### 4.1 创建 Review 任务

```http
POST /api/v1/review/jobs
```

#### 功能说明

接收 GitHub PR URL，创建一次 AI Review 分析任务。

MVP 阶段支持公开 GitHub 仓库 PR。

#### 请求体

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

#### 请求字段说明

| 字段               | 类型    | 必填 | 说明                                 |
| ------------------ | ------- | ---: | ------------------------------------ |
| pr_url             | string  |   是 | GitHub PR 链接                       |
| config             | object  |   否 | Review 配置                          |
| config.enable_ast  | boolean |   否 | 是否启用 AST 方法级上下文，默认 true |
| config.enable_rag  | boolean |   否 | 是否启用 RAG，MVP 默认 false         |
| config.strict_mode | boolean |   否 | 是否启用严格审查模式，默认 true      |

#### 响应示例

```json
{
  "code": 20200,
  "message": "review job created",
  "data": {
    "job_id": "rev_8f9a2b1c",
    "status": "pending",
    "stream_url": "/api/v1/review/stream/rev_8f9a2b1c",
    "report_url": "/api/v1/review/jobs/rev_8f9a2b1c"
  }
}
```

#### 任务状态枚举

| 状态      | 说明                 |
| --------- | -------------------- |
| pending   | 任务已创建，等待执行 |
| running   | 正在分析             |
| completed | 分析完成             |
| failed    | 分析失败             |
| cancelled | 已取消               |

---

### 4.2 获取 Review 任务详情与最终报告

```http
GET /api/v1/review/jobs/{job_id}
```

#### 功能说明

根据 `job_id` 查询 Review 任务详情。

如果任务已完成，返回完整 Review 报告。  
如果任务仍在运行，返回当前进度和已发现的问题。

#### 响应示例：任务进行中

```json
{
  "code": 20000,
  "message": "success",
  "data": {
    "job_id": "rev_8f9a2b1c",
    "status": "running",
    "progress": {
      "step": "SECURITY_AGENT",
      "percent": 65,
      "message": "Security Agent 正在分析安全风险"
    },
    "findings": [
      {
        "id": "finding_001",
        "agent": "SecurityAgent",
        "type": "SQL_INJECTION",
        "level": "HIGH",
        "confidence": 0.92,
        "file": "src/mapper/order_mapper.xml",
        "line": 18,
        "symbol": "selectOrderByUserId",
        "description": "使用 ${userId} 拼接 SQL，存在注入风险。",
        "suggestion": "改为 #{userId} 参数绑定。"
      }
    ],
    "report": null
  }
}
```

#### 响应示例：任务完成

```json
{
  "code": 20000,
  "message": "success",
  "data": {
    "job_id": "rev_8f9a2b1c",
    "status": "completed",
    "pr": {
      "owner": "owner",
      "repo": "repo",
      "number": 101,
      "title": "feat: add order creation flow",
      "author": "octocat",
      "base_branch": "main",
      "head_branch": "feature/order-create",
      "html_url": "https://github.com/owner/repo/pull/101"
    },
    "report": {
      "summary": "本次 PR 新增订单创建流程，并调整库存校验逻辑。",
      "risk_level": "MEDIUM",
      "stats": {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 1,
        "suggestion": 2
      },
      "changed_files": [
        {
          "filename": "src/services/order_service.py",
          "status": "modified",
          "additions": 32,
          "deletions": 8,
          "risk_count": 2
        }
      ],
      "changed_symbols": [
        {
          "file": "src/services/order_service.py",
          "symbol": "OrderService.create_order",
          "language": "python",
          "start_line": 32,
          "end_line": 78,
          "changed_lines": [45, 46]
        }
      ],
      "findings": [
        {
          "id": "finding_001",
          "agent": "PerformanceAgent",
          "type": "N_PLUS_ONE_QUERY",
          "level": "MEDIUM",
          "confidence": 0.86,
          "file": "src/services/order_service.py",
          "line": 45,
          "symbol": "OrderService.create_order",
          "description": "循环中多次访问数据库，可能造成 N+1 查询问题。",
          "suggestion": "建议改为批量查询。",
          "code_snippet": "for id in user_ids:\n    user = user_repo.get_by_id(id)"
        }
      ],
      "review_comment": "## AI Review Summary\n\n本次 PR 整体风险等级：MEDIUM..."
    },
    "created_at": "2026-05-29T10:00:00+08:00",
    "completed_at": "2026-05-29T10:01:32+08:00",
    "updated_at": "2026-05-29T10:01:32+08:00",
    "error_message": null
  }
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| job_id | string | 任务 ID |
| status | string | 任务状态 |
| pr | PullRequestInfo \| null | PR 基本信息（运行中可能为 null） |
| progress | ReviewProgress \| null | 当前进度 |
| findings | Finding[] | 已发现的风险列表 |
| report | ReviewReport \| null | 完整报告（任务完成后非 null） |
| created_at | string | 创建时间 |
| completed_at | string \| null | 完成时间 |
| updated_at | string \| null | 最后更新时间 |
| error_message | string \| null | 错误信息（失败时有值） |

---

### 4.3 获取 Review 任务列表

```http
GET /api/v1/review/jobs
```

#### 功能说明

获取历史 Review 任务列表。

MVP 可选接口。若第一版不做历史列表，可暂时保留接口设计。

#### Query 参数

| 参数      | 类型   | 必填 | 默认值 | 说明           |
| --------- | ------ | ---: | -----: | -------------- |
| page      | number |   否 |      1 | 页码           |
| page_size | number |   否 |     10 | 每页数量       |
| status    | string |   否 |      - | 按任务状态筛选 |

#### 响应示例

```json
{
  "code": 20000,
  "message": "success",
  "data": {
    "items": [
      {
        "job_id": "rev_8f9a2b1c",
        "status": "completed",
        "pr_title": "feat: add order creation flow",
        "pr_url": "https://github.com/owner/repo/pull/101",
        "risk_level": "MEDIUM",
        "finding_count": 6,
        "created_at": "2026-05-29T10:00:00+08:00"
      }
    ],
    "page": 1,
    "page_size": 10,
    "total": 1
  }
}
```

---

### 4.4 取消 Review 任务

```http
POST /api/v1/review/jobs/{job_id}/cancel
```

#### 功能说明

取消尚未完成的 Review 任务。

MVP 可选接口。

#### 响应示例

```json
{
  "code": 20000,
  "message": "review job cancelled",
  "data": {
    "job_id": "rev_8f9a2b1c",
    "status": "cancelled"
  }
}
```

---

## 5. SSE 流式接口

### 5.1 订阅 Review 任务流

```http
GET /api/v1/review/stream/{job_id}
```

#### 功能说明

通过 SSE 实时接收 Review 分析过程。

前端可基于 `EventSource` 监听不同事件类型：

```text
progress
chunk
finding
warning
done
error
```

---

### 5.2 前端调用示例

```ts
const eventSource = new EventSource(`/api/v1/review/stream/${jobId}`);

eventSource.addEventListener("progress", (event) => {
  const data = JSON.parse(event.data);
  console.log("progress", data);
});

eventSource.addEventListener("finding", (event) => {
  const data = JSON.parse(event.data);
  console.log("finding", data);
});

eventSource.addEventListener("done", (event) => {
  const data = JSON.parse(event.data);
  console.log("done", data);
  eventSource.close();
});
```

---

### 5.3 progress 事件

用于展示当前分析进度。

```text
event: progress
data: {"step":"AST_CONTEXT","percent":35,"message":"正在定位变更方法"}
```

| 字段    | 类型   | 说明           |
| ------- | ------ | -------------- |
| step    | string | 当前执行步骤   |
| percent | number | 当前进度百分比 |
| message | string | 进度说明       |

#### step 枚举

| step              | 说明                 |
| ----------------- | -------------------- |
| FETCH_PR          | 拉取 GitHub PR 信息  |
| DIFF_FILTER       | 过滤无效 Diff        |
| DIFF_PARSE        | 解析 Diff            |
| AST_CONTEXT       | AST 方法级上下文提取 |
| SUMMARY_AGENT     | PR 摘要分析          |
| SECURITY_AGENT    | 安全风险分析         |
| PERFORMANCE_AGENT | 性能风险分析         |
| TEST_AGENT        | 测试建议分析         |
| RISK_JUDGE        | 风险仲裁             |
| REPORT_AGENT      | 报告生成             |
| DONE              | 任务完成             |

---

### 5.4 chunk 事件

用于流式输出摘要或最终报告文本片段。

```text
event: chunk
data: {"target":"summary","content":"本次 PR 主要新增订单创建流程"}
```

| 字段    | 类型   | 说明                            |
| ------- | ------ | ------------------------------- |
| target  | string | 输出目标，例如 summary / report |
| content | string | 文本片段                        |

---

### 5.5 finding 事件

用于实时推送发现的风险。

```text
event: finding
data: {
  "id": "finding_001",
  "agent": "SecurityAgent",
  "file": "src/mapper/order_mapper.xml",
  "line": 18,
  "symbol": "selectOrderByUserId",
  "level": "HIGH",
  "type": "SQL_INJECTION",
  "confidence": 0.92,
  "description": "使用 ${userId} 拼接 SQL，存在注入风险。",
  "suggestion": "改为 #{userId} 参数绑定。"
}
```

| 字段        | 类型   | 说明               |
| ----------- | ------ | ------------------ |
| id          | string | 风险 ID            |
| agent       | string | 发现该问题的 Agent |
| file        | string | 文件路径           |
| line        | number | 风险所在行号       |
| symbol      | string | 所属函数/方法      |
| level       | string | 风险等级           |
| type        | string | 风险类型           |
| confidence  | number | 置信度，0 到 1     |
| description | string | 问题描述           |
| suggestion  | string | 修复建议           |

---

### 5.6 warning 事件

用于推送非致命异常。

```text
event: warning
data: {
  "code": "AST_PARSE_FAILED",
  "message": "src/utils/legacy.js AST 解析失败，已降级为纯 Diff 分析。",
  "file": "src/utils/legacy.js"
}
```

---

### 5.7 done 事件

用于标记任务完成。

```text
event: done
data: {
  "job_id": "rev_8f9a2b1c",
  "status": "completed",
  "report_url": "/api/v1/review/jobs/rev_8f9a2b1c",
  "total_findings": 6,
  "duration_ms": 92340
}
```

---

### 5.8 error 事件

用于推送致命错误，收到后前端应关闭 EventSource。

```text
event: error
data: {
  "code": 50200,
  "message": "LLM service failed",
  "detail": "model request timeout"
}
```

---

## 6. GitHub PR 辅助接口

### 6.1 解析 PR URL

```http
POST /api/v1/github/parse-pr-url
```

#### 功能说明

解析 GitHub PR URL，返回 owner、repo、pull_number。

#### 请求体

```json
{
  "pr_url": "https://github.com/owner/repo/pull/101"
}
```

#### 响应示例

```json
{
  "code": 20000,
  "message": "success",
  "data": {
    "owner": "owner",
    "repo": "repo",
    "pull_number": 101,
    "html_url": "https://github.com/owner/repo/pull/101"
  }
}
```

---

### 6.2 预览 PR 基本信息

```http
POST /api/v1/github/pr-preview
```

#### 功能说明

拉取 PR 基本信息，不启动 AI Review。

可用于用户点击“开始分析”前展示确认信息。

#### 请求体

```json
{
  "pr_url": "https://github.com/owner/repo/pull/101"
}
```

#### 响应示例

```json
{
  "code": 20000,
  "message": "success",
  "data": {
    "owner": "owner",
    "repo": "repo",
    "number": 101,
    "title": "feat: add order creation flow",
    "author": "octocat",
    "base_branch": "main",
    "head_branch": "feature/order-create",
    "changed_files": 4,
    "additions": 120,
    "deletions": 32,
    "html_url": "https://github.com/owner/repo/pull/101"
  }
}
```

---

## 7. 数据模型定义

### 7.1 ReviewJob

```ts
type ReviewJob = {
  job_id: string;
  pr_url: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  progress: ReviewProgress;
  config: ReviewConfig;
  created_at: string;
  updated_at: string;
  completed_at?: string;
};
```

### 7.2 ReviewConfig

```ts
type ReviewConfig = {
  enable_ast: boolean;
  enable_rag: boolean;
  strict_mode: boolean;
};
```

### 7.3 ReviewProgress

```ts
type ReviewProgress = {
  step: string;
  percent: number;
  message: string;
};
```

### 7.4 PullRequestInfo

```ts
type PullRequestInfo = {
  owner: string;
  repo: string;
  number: number;
  title: string;
  author: string;
  base_branch: string;
  head_branch: string;
  changed_files: number;
  additions: number;
  deletions: number;
  html_url: string;
};
```

### 7.5 ChangedFile

```ts
type ChangedFile = {
  filename: string;
  status: "added" | "modified" | "removed" | "renamed";
  additions: number;
  deletions: number;
  changes: number;
  patch?: string;
  risk_count?: number;
};
```

### 7.6 ChangedSymbol

```ts
type ChangedSymbol = {
  file: string;
  symbol: string;
  language: string;
  start_line: number;
  end_line: number;
  changed_lines: number[];
  code?: string;
};
```

### 7.7 Finding

```ts
type Finding = {
  id: string;
  agent:
    | "SummaryAgent"
    | "SecurityAgent"
    | "PerformanceAgent"
    | "TestAgent"
    | "RiskJudge"
    | "ReportAgent";
  type: string;
  level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "SUGGESTION";
  confidence: number;
  file: string;
  line: number;
  symbol?: string;
  description: string;
  suggestion: string;
  code_snippet?: string;
};
```

### 7.8 ReviewReport

```ts
type ReviewReport = {
  summary: string;
  risk_level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "PASS";
  stats: {
    critical: number;
    high: number;
    medium: number;
    low: number;
    suggestion: number;
  };
  changed_files: ChangedFile[];
  changed_symbols: ChangedSymbol[];
  findings: Finding[];
  review_comment: string;
};
```

---

## 8. 风险类型枚举

| type              | 说明                 |
| ----------------- | -------------------- |
| SQL_INJECTION     | SQL 注入风险         |
| XSS               | XSS 风险             |
| SECRET_LEAK       | 敏感信息泄露         |
| AUTH_BYPASS       | 权限绕过             |
| N_PLUS_ONE_QUERY  | N+1 查询             |
| LOOP_DB_QUERY     | 循环中查数据库       |
| REDIS_NO_EXPIRE   | Redis 缓存无过期时间 |
| LONG_TRANSACTION  | 长事务               |
| MISSING_TEST      | 缺少测试             |
| EDGE_CASE_MISSING | 边界条件缺失         |
| LARGE_METHOD      | 方法过长             |
| LAYER_VIOLATION   | 分层职责不清         |
| UNKNOWN           | 未分类风险           |

---

## 9. Agent 名称枚举

| agent            | 说明           |
| ---------------- | -------------- |
| SummaryAgent     | PR 摘要 Agent  |
| SecurityAgent    | 安全审查 Agent |
| PerformanceAgent | 性能审查 Agent |
| TestAgent        | 测试审查 Agent |
| RiskJudge        | 风险仲裁 Agent |
| ReportAgent      | 报告生成 Agent |

---

## 10. 前端接口调用流程

```text
用户输入 PR URL
    ↓
POST /api/v1/review/jobs
    ↓
获取 job_id 和 stream_url
    ↓
GET /api/v1/review/stream/{job_id}
    ↓
监听 progress / finding / chunk / done
    ↓
done 后调用 GET /api/v1/review/jobs/{job_id}
    ↓
渲染最终报告
```

---

## 11. 前端伪代码

```ts
async function startReview(prUrl: string) {
  const res = await fetch("/api/v1/review/jobs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      pr_url: prUrl,
      config: {
        enable_ast: true,
        enable_rag: false,
        strict_mode: true,
      },
    }),
  });

  const result = await res.json();
  const { job_id, stream_url } = result.data;

  const eventSource = new EventSource(stream_url);

  eventSource.addEventListener("progress", handleProgress);
  eventSource.addEventListener("finding", handleFinding);
  eventSource.addEventListener("chunk", handleChunk);

  eventSource.addEventListener("done", async () => {
    eventSource.close();
    const report = await fetch(`/api/v1/review/jobs/${job_id}`);
    renderReport(await report.json());
  });
}
```

---

## 12. 后端模块与接口对应关系

| 接口                        | 后端模块                                       |
| --------------------------- | ---------------------------------------------- |
| GET /health                 | api/health.py                                  |
| POST /review/jobs           | api/review.py + services/review_job_service.py |
| GET /review/jobs/{job_id}   | api/review.py + services/report_service.py     |
| GET /review/stream/{job_id} | api/review.py + services/sse_service.py        |
| POST /github/parse-pr-url   | api/github.py + services/github_service.py     |
| POST /github/pr-preview     | api/github.py + services/github_service.py     |

---

## 13. MVP 第一阶段接口实现顺序

第一天建议实现：

```text
1. GET /api/v1/health
2. POST /api/v1/review/jobs
```

第二天实现：

```text
3. POST /api/v1/github/parse-pr-url
4. POST /api/v1/github/pr-preview
5. GET /api/v1/review/stream/{job_id} mock SSE
```

第三天以后逐步接入真实流程：

```text
6. GitHub PR 拉取
7. DiffFilter
8. Diff Parser
9. AST Context
10. LangGraph Agent Workflow
11. GET /api/v1/review/jobs/{job_id}
```

---

## 14. OpenAPI 标签规划

FastAPI Swagger 可按以下 Tag 分组：

| Tag    | 说明           |
| ------ | -------------- |
| Health | 服务状态       |
| Review | Review 任务    |
| Stream | SSE 流式推送   |
| GitHub | GitHub PR 辅助 |
| Report | Review 报告    |

---

## 15. 环境变量

`.env.example` 建议：

```env
APP_NAME=ReviewMind
APP_ENV=development
APP_VERSION=1.0.0

API_PREFIX=/api/v1

GITHUB_TOKEN=

LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=deepseek-chat

DATABASE_URL=postgresql+asyncpg://reviewmind:reviewmind@localhost:5432/reviewmind

REDIS_URL=redis://localhost:6379/0

ENABLE_AST=true
ENABLE_RAG=false
```

---

## 16. 接口安全说明

MVP 阶段可以先不做用户登录，但需要注意：

1. 不要把 GitHub Token 返回给前端。
2. 不要把 LLM API Key 返回给前端。
3. 后端日志避免打印完整密钥。
4. 对 PR URL 做格式校验。
5. 对超大 PR 做 DiffFilter 和大小限制。
6. 对外部 API 调用设置超时。

---

## 17. Curl 调试示例

### 健康检查

```bash
curl http://localhost:8000/api/v1/health
```

### 创建 Review 任务

```bash
curl -X POST http://localhost:8000/api/v1/review/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "pr_url": "https://github.com/owner/repo/pull/101",
    "config": {
      "enable_ast": true,
      "enable_rag": false,
      "strict_mode": true
    }
  }'
```

### 查询 Review 报告

```bash
curl http://localhost:8000/api/v1/review/jobs/rev_8f9a2b1c
```

### 订阅 SSE

```bash
curl -N http://localhost:8000/api/v1/review/stream/rev_8f9a2b1c
```

---

## 18. 最终说明

本接口文档服务于 ReviewMind v1.0 MVP。

第一阶段优先实现：

1. Review Job 创建。
2. SSE 实时进度。
3. GitHub PR 拉取。
4. Diff 与 AST 上下文。
5. 多 Agent Review。
6. 结构化报告查询。

后续版本可继续扩展：

- GitHub App Webhook
- 自动评论 PR
- 用户登录
- 团队规范知识库
- pgvector RAG
- 历史 Review Memory
