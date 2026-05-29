import type {
  JobDetailResponse,
  CreateJobResponse,
  PullRequestInfo,
  ReviewReport,
  Finding,
  ChangedFile,
  ChangedSymbol,
  ProgressEvent,
  ChunkEvent,
  FindingEvent,
  WarningEvent,
  DoneEvent,
} from '../types';

export const MOCK_PR_URL = 'https://github.com/octocat/hello-world/pull/42';

// ============ PR Info ============
export const mockPullRequest: PullRequestInfo = {
  owner: 'octocat',
  repo: 'hello-world',
  number: 42,
  title: 'feat: add order creation flow with inventory validation',
  author: 'octocat',
  base_branch: 'main',
  head_branch: 'feature/order-create',
  changed_files: 5,
  additions: 156,
  deletions: 32,
  html_url: MOCK_PR_URL,
};

// ============ Create Job Response ============
export const mockCreateJobResponse: CreateJobResponse = {
  job_id: 'rev_demo001',
  status: 'pending',
  stream_url: '/api/v1/review/stream/rev_demo001',
  report_url: '/api/v1/review/jobs/rev_demo001',
};

// ============ Changed Files ============
export const mockChangedFiles: ChangedFile[] = [
  {
    filename: 'src/services/order_service.py',
    status: 'modified',
    additions: 45,
    deletions: 8,
    changes: 53,
    risk_count: 2,
    old_code: `class OrderService:
    def create_order(self, user_id: int, items: list[OrderItem]) -> Order:
        """Create a new order with inventory validation."""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        total = 0
        for item in items:
            if item.quantity <= 0:
                raise ValidationError("Invalid quantity")

            total += item.price * item.quantity

        order = Order(user_id=user_id, items=items, total=total)
        return self.order_repo.save(order)`,
    new_code: `class OrderService:
    def create_order(self, user_id: int, items: list[OrderItem]) -> Order:
        """Create a new order with inventory validation."""
        user = self.user_repo.get_by_id_with_orders(user_id)
        if not user:
            raise NotFoundError("User not found")

        total = 0
        for item in items:
            if item.quantity <= 0:
                raise ValidationError("Invalid quantity")

            # Check inventory
            inventory = self.inventory_repo.get_by_product_id(item.product_id)
            if inventory.available < item.quantity:
                raise InsufficientStockError(f"Insufficient stock for {item.product_id}")

            total += item.price * item.quantity

        order = Order(user_id=user_id, items=items, total=total)
        return self.order_repo.save(order)`,
    patch: `@@ -30,7 +30,7 @@ class OrderService:
     def create_order(self, user_id: int, items: list[OrderItem]) -> Order:
         """Create a new order with inventory validation."""
-        user = self.user_repo.get_by_id(user_id)
+        user = self.user_repo.get_by_id_with_orders(user_id)
         if not user:
             raise NotFoundError("User not found")

@@ -42,6 +42,10 @@ class OrderService:
             if item.quantity <= 0:
                 raise ValidationError("Invalid quantity")

+            # Check inventory
+            inventory = self.inventory_repo.get_by_product_id(item.product_id)
+            if inventory.available < item.quantity:
+                raise InsufficientStockError(f"Insufficient stock for {item.product_id}")
+
             total += item.price * item.quantity

         order = Order(user_id=user_id, items=items, total=total)`,
  },
  {
    filename: 'src/mapper/order_mapper.xml',
    status: 'modified',
    additions: 8,
    deletions: 2,
    changes: 10,
    risk_count: 1,
    old_code: `<mapper namespace="order">
    <select id="selectOrderByUserId" resultMap="orderResultMap">
        SELECT * FROM orders WHERE user_id = \${userId}
    </select>
</mapper>`,
    new_code: `<mapper namespace="order">
    <select id="selectOrderByUserId" resultMap="orderResultMap">
        SELECT * FROM orders WHERE user_id = \${userId} AND status != 'deleted'
    </select>

    <select id="selectOrdersByIds" resultMap="orderResultMap">
        SELECT * FROM orders WHERE id IN
        <foreach collection="ids" item="id" open="(" separator="," close=")">
            #{id}
        </foreach>
    </select>
</mapper>`,
    patch: `@@ -15,9 +15,15 @@
     <select id="selectOrderByUserId" resultMap="orderResultMap">
-        SELECT * FROM orders WHERE user_id = \${userId}
+        SELECT * FROM orders WHERE user_id = \${userId} AND status != 'deleted'
     </select>
+
+    <select id="selectOrdersByIds" resultMap="orderResultMap">
+        SELECT * FROM orders WHERE id IN
+        <foreach collection="ids" item="id" open="(" separator="," close=")">
+            #{id}
+        </foreach>
+    </select>`,
  },
  {
    filename: 'src/controllers/order_controller.py',
    status: 'modified',
    additions: 22,
    deletions: 4,
    changes: 26,
    risk_count: 1,
  },
  {
    filename: 'tests/test_order_service.py',
    status: 'added',
    additions: 65,
    deletions: 0,
    changes: 65,
  },
  {
    filename: 'src/utils/validator.py',
    status: 'modified',
    additions: 16,
    deletions: 18,
    changes: 34,
  },
];

// ============ Changed Symbols ============
export const mockChangedSymbols: ChangedSymbol[] = [
  {
    file: 'src/services/order_service.py',
    symbol: 'OrderService.create_order',
    language: 'python',
    start_line: 32,
    end_line: 78,
    changed_lines: [34, 45, 46, 47, 48, 49],
    code: `def create_order(self, user_id: int, items: list[OrderItem]) -> Order:
    """Create a new order with inventory validation."""
    user = self.user_repo.get_by_id_with_orders(user_id)
    if not user:
        raise NotFoundError("User not found")

    total = 0
    for item in items:
        if item.quantity <= 0:
            raise ValidationError("Invalid quantity")

        # Check inventory
        inventory = self.inventory_repo.get_by_product_id(item.product_id)
        if inventory.available < item.quantity:
            raise InsufficientStockError(f"Insufficient stock for {item.product_id}")

        total += item.price * item.quantity

    order = Order(user_id=user_id, items=items, total=total)
    return self.order_repo.save(order)`,
  },
  {
    file: 'src/mapper/order_mapper.xml',
    symbol: 'selectOrderByUserId',
    language: 'xml',
    start_line: 15,
    end_line: 18,
    changed_lines: [16],
  },
  {
    file: 'src/controllers/order_controller.py',
    symbol: 'OrderController.create',
    language: 'python',
    start_line: 22,
    end_line: 58,
    changed_lines: [28, 29, 30, 31, 32],
  },
];

// ============ Findings ============
export const mockFindings: Finding[] = [
  {
    id: 'finding_001',
    agent: 'SecurityAgent',
    type: 'SQL_INJECTION',
    level: 'HIGH',
    confidence: 0.92,
    file: 'src/mapper/order_mapper.xml',
    line: 16,
    symbol: 'selectOrderByUserId',
    description:
      '使用 ${userId} 字符串拼接构造 SQL 查询条件，存在 SQL 注入风险。攻击者可能通过构造特殊 userId 值注入恶意 SQL 片段。',
    suggestion: '将 ${userId} 改为 #{userId}，使用 MyBatis 参数绑定机制防止注入。',
    code_snippet: `SELECT * FROM orders WHERE user_id = \${userId} AND status != 'deleted'`,
  },
  {
    id: 'finding_002',
    agent: 'PerformanceAgent',
    type: 'N_PLUS_ONE_QUERY',
    level: 'MEDIUM',
    confidence: 0.86,
    file: 'src/services/order_service.py',
    line: 46,
    symbol: 'OrderService.create_order',
    description:
      '在遍历 items 的循环中，每次迭代都调用 inventory_repo.get_by_product_id() 单独查询数据库，当 items 数量较大时会产生 N+1 查询问题。',
    suggestion:
      '建议改为批量查询：在循环前一次性调用 inventory_repo.get_by_product_ids() 获取所有产品库存，然后在内存中匹配。',
    code_snippet: `for item in items:
    # 循环内单独查库 - N+1 问题
    inventory = self.inventory_repo.get_by_product_id(item.product_id)`,
  },
  {
    id: 'finding_003',
    agent: 'PerformanceAgent',
    type: 'LOOP_DB_QUERY',
    level: 'LOW',
    confidence: 0.78,
    file: 'src/services/order_service.py',
    line: 46,
    symbol: 'OrderService.create_order',
    description: '循环中查询数据库，虽然单次查询开销不大，但在高并发场景下可能造成数据库连接池压力。',
    suggestion: '使用批量查询替代循环内单条查询，减少数据库连接开销。',
  },
  {
    id: 'finding_004',
    agent: 'TestAgent',
    type: 'MISSING_TEST',
    level: 'MEDIUM',
    confidence: 0.85,
    file: 'src/services/order_service.py',
    line: 47,
    symbol: 'OrderService.create_order',
    description:
      '新增的库存不足异常分支（InsufficientStockError）没有对应的测试覆盖。如果库存逻辑有 Bug，可能导致超卖或错误拒绝订单。',
    suggestion:
      '建议补充以下测试场景：1) 库存充足时正常创建订单 2) 库存不足时抛出异常 3) 部分商品库存不足 4) 库存刚好等于订单数量（边界条件）。',
  },
  {
    id: 'finding_005',
    agent: 'TestAgent',
    type: 'EDGE_CASE_MISSING',
    level: 'LOW',
    confidence: 0.72,
    file: 'src/services/order_service.py',
    line: 41,
    symbol: 'OrderService.create_order',
    description: '未处理 items 为空列表的边界情况，可能导致生成 total 为 0 的无效订单。',
    suggestion: '在方法开头添加空列表检查：if not items: raise ValidationError("Order must have at least one item")',
  },
  {
    id: 'finding_006',
    agent: 'SecurityAgent',
    type: 'SECRET_LEAK',
    level: 'LOW',
    confidence: 0.45,
    file: 'src/controllers/order_controller.py',
    line: 28,
    symbol: 'OrderController.create',
    description: '日志中打印了完整的订单请求体，可能包含敏感的用户信息（如收货地址、手机号）。',
    suggestion: '对敏感字段进行脱敏处理后再记录日志，或仅记录订单 ID 和金额等非敏感信息。',
  },
];

// ============ Review Report ============
export const mockReport: ReviewReport = {
  summary:
    '本次 PR 新增订单创建流程，主要修改了 OrderService.create_order 方法，增加了库存校验逻辑，并在 OrderController 中暴露了新的 REST API 端点。同时新增了订单 MyBatis 映射文件和基础测试文件。整体代码结构清晰，但存在 SQL 注入风险和 N+1 查询问题需要优先修复。',
  risk_level: 'MEDIUM',
  stats: {
    critical: 0,
    high: 1,
    medium: 2,
    low: 3,
    suggestion: 0,
  },
  changed_files: mockChangedFiles,
  changed_symbols: mockChangedSymbols,
  findings: mockFindings,
  review_comment: `## AI Review Summary

**PR:** feat: add order creation flow with inventory validation (#42)
**Author:** octocat
**Risk Level:** MEDIUM
**Review Date:** 2026-05-29

### Overview
本次 PR 新增订单创建流程，核心变更集中在 OrderService.create_order 方法。代码结构清晰，业务逻辑合理，但存在以下需要关注的问题。

### High Risk
- **SQL Injection in order_mapper.xml:16** — \`selectOrderByUserId\` 使用 \`\${userId}\` 字符串拼接构造 SQL，存在注入风险。建议改为 \`#{userId}\` 参数绑定。

### Medium Risk
- **N+1 Query in order_service.py:46** — 循环内逐条查询库存，建议改为批量查询。
- **Missing Test for InsufficientStockError** — 新增的库存不足异常分支缺少测试覆盖。

### Low Risk
- **Edge Case: empty items list** — 未处理空订单商品的边界情况。
- **Sensitive data in logs** — 日志中打印了完整请求体，建议脱敏。

### Recommendation
建议优先修复 HIGH 级别的 SQL 注入问题，然后处理 N+1 查询和测试补充。整体代码质量良好，修复上述问题后即可合并。`,
};

// ============ Running State ============
export const mockJobRunning: JobDetailResponse = {
  job_id: 'rev_demo001',
  status: 'running',
  pr: mockPullRequest,
  report: { ...mockReport, findings: mockFindings.slice(0, 1) } as ReviewReport,
  progress: {
    step: 'SECURITY_AGENT',
    percent: 45,
    message: 'Security Agent 正在分析安全风险...',
  },
  findings: mockFindings.slice(0, 1),
  created_at: new Date().toISOString(),
};

// ============ Completed State ============
export const mockJobCompleted: JobDetailResponse = {
  job_id: 'rev_demo001',
  status: 'completed',
  pr: mockPullRequest,
  report: mockReport,
  created_at: new Date(Date.now() - 92000).toISOString(),
  completed_at: new Date().toISOString(),
};

// ============ SSE Event Sequence ============
export interface MockSSEEvent {
  delayMs: number;
  event: string;
  data: ProgressEvent | FindingEvent | ChunkEvent | WarningEvent | DoneEvent;
}

export const mockSSESequence: MockSSEEvent[] = [
  {
    delayMs: 300,
    event: 'progress',
    data: { step: 'FETCH_PR', percent: 5, message: '正在拉取 GitHub PR 信息...' },
  },
  {
    delayMs: 600,
    event: 'progress',
    data: { step: 'DIFF_FILTER', percent: 12, message: '正在过滤无效 Diff 文件...' },
  },
  {
    delayMs: 400,
    event: 'progress',
    data: { step: 'DIFF_PARSE', percent: 20, message: '正在解析 Diff 变更行...' },
  },
  {
    delayMs: 700,
    event: 'progress',
    data: { step: 'AST_CONTEXT', percent: 30, message: '正在提取 AST 方法级上下文...' },
  },
  {
    delayMs: 200,
    event: 'warning',
    data: {
      code: 'AST_PARSE_FAILED',
      message: 'src/utils/legacy.js AST 解析失败，已降级为纯 Diff 分析。',
      file: 'src/utils/legacy.js',
    },
  },
  {
    delayMs: 600,
    event: 'progress',
    data: { step: 'SUMMARY_AGENT', percent: 40, message: 'Summary Agent 正在分析 PR 意图...' },
  },
  {
    delayMs: 300,
    event: 'chunk',
    data: { target: 'summary', content: '本次 PR 主要新增订单创建流程，' },
  },
  {
    delayMs: 200,
    event: 'chunk',
    data: { target: 'summary', content: '涉及 OrderService.create_order 与 OrderRepository.save_order。' },
  },
  {
    delayMs: 200,
    event: 'chunk',
    data: { target: 'summary', content: '主要影响订单创建、库存校验和支付初始化逻辑。' },
  },
  {
    delayMs: 500,
    event: 'progress',
    data: { step: 'SECURITY_AGENT', percent: 55, message: 'Security Agent 正在分析安全风险...' },
  },
  {
    delayMs: 800,
    event: 'finding',
    data: {
      id: 'finding_001',
      agent: 'SecurityAgent',
      type: 'SQL_INJECTION',
      level: 'HIGH',
      confidence: 0.92,
      file: 'src/mapper/order_mapper.xml',
      line: 16,
      symbol: 'selectOrderByUserId',
      description: '使用 ${userId} 字符串拼接构造 SQL 查询条件，存在 SQL 注入风险。',
      suggestion: '将 ${userId} 改为 #{userId}，使用 MyBatis 参数绑定机制防止注入。',
    },
  },
  {
    delayMs: 700,
    event: 'progress',
    data: { step: 'PERFORMANCE_AGENT', percent: 65, message: 'Performance Agent 正在分析性能风险...' },
  },
  {
    delayMs: 600,
    event: 'finding',
    data: {
      id: 'finding_002',
      agent: 'PerformanceAgent',
      type: 'N_PLUS_ONE_QUERY',
      level: 'MEDIUM',
      confidence: 0.86,
      file: 'src/services/order_service.py',
      line: 46,
      symbol: 'OrderService.create_order',
      description: '循环中多次访问数据库，可能造成 N+1 查询问题。',
      suggestion: '建议改为批量查询：在循环前一次性获取所有产品库存。',
    },
  },
  {
    delayMs: 300,
    event: 'finding',
    data: {
      id: 'finding_003',
      agent: 'PerformanceAgent',
      type: 'LOOP_DB_QUERY',
      level: 'LOW',
      confidence: 0.78,
      file: 'src/services/order_service.py',
      line: 46,
      symbol: 'OrderService.create_order',
      description: '循环中查询数据库，高并发场景下可能造成连接池压力。',
      suggestion: '使用批量查询替代循环内单条查询。',
    },
  },
  {
    delayMs: 700,
    event: 'progress',
    data: { step: 'TEST_AGENT', percent: 75, message: 'Test Agent 正在分析测试覆盖...' },
  },
  {
    delayMs: 500,
    event: 'finding',
    data: {
      id: 'finding_004',
      agent: 'TestAgent',
      type: 'MISSING_TEST',
      level: 'MEDIUM',
      confidence: 0.85,
      file: 'src/services/order_service.py',
      line: 47,
      symbol: 'OrderService.create_order',
      description: '新增的库存不足异常分支缺少测试覆盖。',
      suggestion: '补充库存充足、不足、刚好等于、部分不足等测试场景。',
    },
  },
  {
    delayMs: 300,
    event: 'finding',
    data: {
      id: 'finding_005',
      agent: 'TestAgent',
      type: 'EDGE_CASE_MISSING',
      level: 'LOW',
      confidence: 0.72,
      file: 'src/services/order_service.py',
      line: 41,
      symbol: 'OrderService.create_order',
      description: '未处理 items 为空列表的边界情况。',
      suggestion: '添加空列表检查：if not items: raise ValidationError(...)',
    },
  },
  {
    delayMs: 600,
    event: 'progress',
    data: { step: 'RISK_JUDGE', percent: 85, message: 'Risk Judge 正在进行风险仲裁...' },
  },
  {
    delayMs: 500,
    event: 'finding',
    data: {
      id: 'finding_006',
      agent: 'SecurityAgent',
      type: 'SECRET_LEAK',
      level: 'LOW',
      confidence: 0.45,
      file: 'src/controllers/order_controller.py',
      line: 28,
      symbol: 'OrderController.create',
      description: '日志中打印了完整的订单请求体，可能包含敏感用户信息。',
      suggestion: '对敏感字段进行脱敏处理后再记录日志。',
    },
  },
  {
    delayMs: 700,
    event: 'progress',
    data: { step: 'REPORT_AGENT', percent: 95, message: 'Report Agent 正在生成最终报告...' },
  },
  {
    delayMs: 300,
    event: 'chunk',
    data: { target: 'report', content: '## AI Review Summary\n\n本次 PR 整体风险等级：MEDIUM...' },
  },
  {
    delayMs: 600,
    event: 'done',
    data: {
      job_id: 'rev_demo001',
      status: 'completed',
      report_url: '/api/v1/review/jobs/rev_demo001',
      total_findings: 6,
      duration_ms: 8300,
    },
  },
];

// ============ Job List ============
export const mockJobList = {
  items: [
    {
      job_id: 'rev_demo001',
      status: 'completed' as const,
      pr_title: 'feat: add order creation flow with inventory validation',
      pr_url: MOCK_PR_URL,
      risk_level: 'MEDIUM' as const,
      finding_count: 6,
      created_at: new Date(Date.now() - 120000).toISOString(),
    },
    {
      job_id: 'rev_demo002',
      status: 'completed' as const,
      pr_title: 'fix: resolve payment gateway timeout issue',
      pr_url: 'https://github.com/octocat/hello-world/pull/41',
      risk_level: 'LOW' as const,
      finding_count: 2,
      created_at: new Date(Date.now() - 3600000).toISOString(),
    },
  ],
  page: 1,
  page_size: 10,
  total: 2,
};

// ============ GitHub PR Preview ============
export const mockPrPreview = {
  owner: 'octocat',
  repo: 'hello-world',
  number: 42,
  title: 'feat: add order creation flow with inventory validation',
  author: 'octocat',
  base_branch: 'main',
  head_branch: 'feature/order-create',
  changed_files: 5,
  additions: 156,
  deletions: 32,
  html_url: MOCK_PR_URL,
};

// ============ Helper: Simulate API delay ============
export function simulateDelay(ms = 400): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
