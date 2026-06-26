#!/usr/bin/env python3
"""Agent Loop 端到端冒烟测试（真实 LLM + 真实 GitHub API）。

用途：验证 Planner 是否真的会通过原生 Function Calling 调用工具，
并在多轮 ReAct 循环后产出审查计划。

用法（在 backend/ 目录下运行）：
    python ../scripts/smoke_test_agent_loop.py <PR_URL>

示例：
    python ../scripts/smoke_test_agent_loop.py https://github.com/Sxuan-Coder/ReviewMind/pull/54

前置条件：
- backend/.env 中配置了 LLM_API_KEY（真实可用，非 mock）
- LLM_MOCK_MODE=false
- 网络可访问 GitHub API 与 LLM API

输出：
- Planner 每一步的工具调用决策（证明"真的会调工具"）
- 最终产出的审查计划（ReviewPlan）
- Executor 各维度执行结果
- Finalizer 聚合后的报告
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# 让脚本能 import backend.app（从 backend/ 目录运行时）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


async def run(pr_url: str) -> None:
    # 延迟导入，确保 .env 已加载
    from app.agent_loop.executor import Executor
    from app.agent_loop.finalizer import Finalizer
    from app.agent_loop.orchestrator import ReviewOrchestrator
    from app.agent_loop.planner import PlannerAgent
    from app.agent_loop.schemas import ContextSnapshot
    from app.core.config import settings
    from app.core.llm import llm_client
    from app.graph.nodes import (
        node_ast_context,
        node_diff_filter,
        node_fetch_files_async,
        node_fetch_pr_async,
        node_parse_diff,
        node_rag_context,
        node_tech_stack_analysis,
    )
    from app.graph.state import ReviewGraphState
    from app.services.github_client import GitHubClient
    from app.services.review_job_store import ReviewJobStore

    print("=" * 70)
    print("Agent Loop 冒烟测试（真实 LLM + 真实 GitHub API）")
    print("=" * 70)
    print(f"PR URL        : {pr_url}")
    print(f"LLM mock mode : {settings.llm_mock_mode}")
    print(f"LLM configured: {llm_client.is_configured}")
    if settings.llm_mock_mode or not llm_client.is_configured:
        print("\n!!! 警告：LLM 处于 mock 模式或未配置，无法验证真实工具调用 !!!")
        print("!!! 请在 backend/.env 设置 LLM_API_KEY 并令 LLM_MOCK_MODE=false !!!")
        return

    # ---- 第一阶段：真实拉取 PR + 预处理 ----
    print("\n[1/4] 拉取 PR 并预处理...")
    gc = GitHubClient()
    state = ReviewGraphState(job_id="smoke-test", pr_url=pr_url, config={})
    state = await node_fetch_pr_async(state, gc, _NullStore())
    if state.error:
        print(f"  拉取 PR 失败: {state.error}")
        return
    state = await node_fetch_files_async(state, gc, _NullStore())
    state = node_diff_filter(state, gc, _NullStore())
    state = node_parse_diff(state, gc, _NullStore())
    state = node_ast_context(state, gc, _NullStore())
    state = await node_rag_context(state, gc, _NullStore())
    state = node_tech_stack_analysis(state, gc, _NullStore())
    print(f"  标题: {state.pr_info.get('title', 'N/A')}")
    print(f"  变更文件数: {len(state.filtered_files.get('included_files', []))}")

    snapshot = ContextSnapshot(
        job_id="smoke-test", pr_url=pr_url,
        pr_info=state.pr_info, filtered_files=state.filtered_files,
        parsed_diff=state.parsed_diff, ast_contexts=state.ast_contexts,
        rag_contexts=state.rag_contexts, tech_stack_prompt=state.tech_stack_prompt,
        config={},
    )

    # ---- 第二阶段：Planner（真实 LLM，带可视化回调）----
    print("\n[2/4] Planner 运行中（真实 LLM）—— 观察它是否调用工具：")

    async def on_step(step_no, step, tool_result):
        tc = step.tool_call
        print(f"\n  ── 步骤 {step_no} ──")
        if tc:
            print(f"  🔧 模型调用工具: {tc.name}(id={tc.id})")
            print(f"     参数: {tc.arguments}")
            print(f"     工具返回: {tool_result[:200]}")
        else:
            print(f"  ✅ 模型给出最终文本（长度 {len(step.final_text)}）")

    planner = PlannerAgent(snapshot, on_step=on_step, max_steps=5)
    plan = await planner.plan()
    print(f"\n  📋 最终审查计划:")
    print(f"     风险提示: {plan.overall_risk_hint}")
    print(f"     决策理由: {plan.reasoning[:150]}")
    for d in plan.dimensions:
        print(f"     - {d.dimension.value:12s} use_rag={d.use_rag} | {d.rationale[:60]}")

    # ---- 第三阶段：Executor ----
    print("\n[3/4] Executor 并行执行各维度...")
    executor = Executor(snapshot)
    dim_results = await executor.execute(plan)
    for dr in dim_results:
        findings_n = len(dr.result.findings) if dr.result else 0
        status = "✓" if dr.success else "✗"
        print(f"  {status} {dr.dimension.value:12s} findings={findings_n}")
        if not dr.success:
            print(f"      error: {dr.error}")

    # ---- 第四阶段：Finalizer ----
    print("\n[4/4] Finalizer 聚合 + 生成报告...")
    finalizer = Finalizer(snapshot)
    finalized = finalizer.finalize(dim_results, job_id="smoke-test")
    print(f"  风险等级: {finalized.aggregated_risk.risk_level}")
    print(f"  总 findings: {len(finalized.aggregated_risk.findings)}")
    print(f"  去重数: {finalized.aggregated_risk.dedup_count}")
    print(f"  误报丢弃: {finalized.findings_dropped}")
    print("\n  报告摘要:")
    print("  " + finalized.summary_text[:300].replace("\n", "\n  "))

    print("\n" + "=" * 70)
    print("冒烟测试完成。如果上面看到 🔧 标记，说明 Planner 真的通过原生")
    print("Function Calling 调用了工具——这就是「真 Agent」的证据。")
    print("=" * 70)


class _NullStore:
    """空 store：冒烟测试不需要持久化，所有方法 no-op。"""

    async def save_pr_info(self, *a, **k):  # noqa: ARG002
        pass

    async def add_progress_event(self, *a, **k):  # noqa: ARG002
        pass


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python smoke_test_agent_loop.py <PR_URL>")
        sys.exit(1)
    asyncio.run(run(sys.argv[1]))


if __name__ == "__main__":
    main()
