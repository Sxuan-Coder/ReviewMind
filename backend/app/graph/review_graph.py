"""LangGraph Review Workflow：将 pipeline + mock agents 编排为有序图节点。

使用方式：
    graph = ReviewGraph(store, github_client)
    result = await graph.run(job)

图节点顺序：
    fetch_pr → fetch_files → diff_filter → parse_diff → ast_context
    → summary_agent → security_agent → performance_agent → test_agent
    → risk_judge → report_agent

非关键节点（ast_context、各 agent）失败不阻塞整体流程，记录 warning。
关键节点（fetch_pr、fetch_files）失败直接标记 job failed。
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from app.graph.nodes import (
    node_ast_context,
    node_diff_filter,
    node_fetch_files_async,
    node_fetch_pr_async,
    node_parse_diff,
    node_performance_agent,
    node_report_agent,
    node_risk_judge,
    node_security_agent,
    node_summary_agent,
    node_test_agent,
)
from app.graph.state import ReviewGraphState
from app.models.review_job import ReviewJob
from app.schemas.review import (
    ChangedFile,
    ReviewJobStatus,
    ReviewReport,
    ReviewReportStats,
)
from app.services.github_client import GitHubClient
from app.services.review_job_store import ReviewJobStore


logger = logging.getLogger(__name__)


@dataclass
class ReviewGraphResult:
    pr_info: dict[str, Any]
    filtered_files: dict[str, Any]
    parsed_diff: list[dict[str, Any]]
    warnings: list[str]


# 关键节点：失败后不再继续
_CRITICAL_NODES = {"fetch_pr", "fetch_files"}

# 节点执行顺序
_NODE_ORDER = [
    "fetch_pr",
    "fetch_files",
    "diff_filter",
    "parse_diff",
    "ast_context",
    "summary_agent",
    "security_agent",
    "performance_agent",
    "test_agent",
    "risk_judge",
    "report_agent",
]

# 分段执行：pre 串行 → agents 并行 → post 串行
_PRE_NODES = ["fetch_pr", "fetch_files", "diff_filter", "parse_diff", "ast_context"]
_AGENT_NODES = ["summary_agent", "security_agent", "performance_agent", "test_agent"]
_POST_NODES = ["risk_judge", "report_agent"]

# 节点名称 → 显示名（用于 progress 事件）
_NODE_DISPLAY: dict[str, tuple[str, str]] = {
    "fetch_pr": ("FETCH_PR", "正在拉取 GitHub PR 信息"),
    "fetch_files": ("FETCH_FILES", "正在拉取 PR 文件列表"),
    "diff_filter": ("DIFF_FILTER", "正在过滤无意义 Diff"),
    "parse_diff": ("DIFF_PARSE", "正在解析变更行"),
    "ast_context": ("AST_CONTEXT", "正在提取 AST 上下文"),
    "summary_agent": ("SUMMARY_AGENT", "Summary Agent 运行中"),
    "security_agent": ("SECURITY_AGENT", "Security Agent 运行中"),
    "performance_agent": ("PERFORMANCE_AGENT", "Performance Agent 运行中"),
    "test_agent": ("TEST_AGENT", "Test Agent 运行中"),
    "risk_judge": ("RISK_JUDGE", "风险聚合中"),
    "report_agent": ("REPORT_AGENT", "生成报告中"),
}

# 节点百分比
_NODE_PERCENT: dict[str, int] = {
    "fetch_pr": 15,
    "fetch_files": 30,
    "diff_filter": 45,
    "parse_diff": 55,
    "ast_context": 62,
    "summary_agent": 70,
    "security_agent": 75,
    "performance_agent": 80,
    "test_agent": 85,
    "risk_judge": 92,
    "report_agent": 98,
}


class ReviewGraph:
    def __init__(self, store: ReviewJobStore, github_client: GitHubClient | None = None) -> None:
        self._store = store
        self._github_client = github_client or GitHubClient()

    async def run(self, job: ReviewJob) -> ReviewGraphResult:
        """执行完整的 review graph 工作流。

        节点分三段执行：
        - pre   ：串行（节点间有依赖）
        - agents：并行（4 个 Agent 互不依赖，asyncio.gather 并发调用 LLM）
        - post  ：串行（依赖 agent_results）
        """
        state = ReviewGraphState(job_id=job.job_id, pr_url=job.pr_url)
        self._store.update_status(job.job_id, ReviewJobStatus.running)
        logger.info("[GRAPH] Starting pipeline | job=%s pr_url=%s nodes=%d", job.job_id, job.pr_url, len(_NODE_ORDER))

        # --- pre 段：串行执行（fetch/filter/parse/ast） ---
        for node_name in _PRE_NODES:
            if state.error:
                break

            display_step, display_msg = _NODE_DISPLAY.get(node_name, (node_name.upper(), node_name))
            percent = _NODE_PERCENT.get(node_name, 50)
            self._add_progress(job.job_id, display_step, percent, display_msg)
            logger.info("[GRAPH] Running node=%s display=%s", node_name, display_step)

            state = await self._run_node(node_name, state)

            # 在 Diff 解析完成后推送文件列表
            if node_name == "parse_diff" and not state.error:
                included = state.filtered_files.get("included_files", [])
                file_names = [f.get("filename", "") for f in included if isinstance(f, dict)]
                logger.info("[GRAPH] Diff parsed: %d files included -> %s", len(file_names), file_names[:5])
                if file_names:
                    self._store.add_progress_event(
                        job.job_id,
                        {
                            "type": "chunk",
                            "target": "files",
                            "content": json.dumps(file_names, ensure_ascii=False),
                        },
                    )

            if state.error and node_name in _CRITICAL_NODES:
                logger.error("[GRAPH] Critical node %s FAILED | error=%s", node_name, state.error)
                self._store.update_status(job.job_id, ReviewJobStatus.failed, error_message=state.error)
                self._add_progress(
                    job.job_id, f"{display_step}_FAILED", percent,
                    state.error,
                    event_type="warning",
                )
                return ReviewGraphResult(
                    pr_info=state.pr_info,
                    filtered_files=state.filtered_files,
                    parsed_diff=state.parsed_diff,
                    warnings=state.warnings,
                )

        # --- agents 段：并行执行（互不依赖，各自调用 LLM） ---
        if not state.error:
            # 并行前推送一次聚合 progress，避免 70/75/80/85 百分比乱序回退
            self._add_progress(job.job_id, "AGENTS", 70, "多 Agent 并行分析中")
            logger.info("[GRAPH] Running %d agents in PARALLEL: %s", len(_AGENT_NODES), _AGENT_NODES)
            results = await asyncio.gather(
                *[self._run_node(node_name, state) for node_name in _AGENT_NODES],
                return_exceptions=True,
            )
            for node_name, res in zip(_AGENT_NODES, results):
                if isinstance(res, Exception):
                    logger.error("[GRAPH] Agent %s raised: %s", node_name, res)
                    state.warnings.append(f"{node_name.upper()}: {res}")
            logger.info("[GRAPH] Agents done | agent_results=%d warnings=%d",
                        len(state.agent_results), len(state.warnings))

        # --- post 段：串行执行（risk_judge → report_agent） ---
        if not state.error:
            for node_name in _POST_NODES:
                display_step, display_msg = _NODE_DISPLAY.get(node_name, (node_name.upper(), node_name))
                percent = _NODE_PERCENT.get(node_name, 50)
                self._add_progress(job.job_id, display_step, percent, display_msg)
                logger.info("[GRAPH] Running node=%s display=%s", node_name, display_step)
                state = await self._run_node(node_name, state)

        # 所有节点完成 → 构建报告
        logger.info("[GRAPH] All nodes done, calling _finish | error=%s warnings=%d", state.error, len(state.warnings))
        self._finish(job.job_id, state)
        return ReviewGraphResult(
            pr_info=state.pr_info,
            filtered_files=state.filtered_files,
            parsed_diff=state.parsed_diff,
            warnings=state.warnings,
        )

    async def _run_node(self, node_name: str, state: ReviewGraphState) -> ReviewGraphState:
        gc = self._github_client
        st = self._store
        # 异步节点（直接 await）
        async_dispatch: dict[str, Any] = {
            "fetch_pr": lambda s: node_fetch_pr_async(s, gc, st),
            "fetch_files": lambda s: node_fetch_files_async(s, gc, st),
            "summary_agent": lambda s: node_summary_agent(s, gc, st),
            "security_agent": lambda s: node_security_agent(s, gc, st),
            "performance_agent": lambda s: node_performance_agent(s, gc, st),
            "test_agent": lambda s: node_test_agent(s, gc, st),
        }
        # 同步节点（用 _sync 包装）
        sync_dispatch: dict[str, Any] = {
            "diff_filter": lambda s: _sync(node_diff_filter, s, gc, st),
            "parse_diff": lambda s: _sync(node_parse_diff, s, gc, st),
            "ast_context": lambda s: _sync(node_ast_context, s, gc, st),
            "risk_judge": lambda s: _sync(node_risk_judge, s, gc, st),
            "report_agent": lambda s: _sync(node_report_agent, s, gc, st),
        }

        if node_name in async_dispatch:
            return await async_dispatch[node_name](state)
        handler = sync_dispatch.get(node_name)
        if handler is not None:
            return await handler(state)
        return state

    def _finish(self, job_id: str, state: ReviewGraphState) -> None:
        """将 graph 输出组装为 ReviewReport 并保存到 store。"""
        changed_files = [
            ChangedFile(
                filename=f["filename"],
                status=f.get("status", "unknown"),
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
                changes=f.get("changes", f.get("additions", 0) + f.get("deletions", 0)),
                patch=f.get("patch"),  # GitHub Diff patch 数据
                risk_count=0,
            )
            for f in state.filtered_files.get("included_files", [])
        ]

        if state.report_output:
            output = state.report_output
            logger.info("[GRAPH] Using report_output branch | summary_len=%d findings=%d risk=%s",
                        len(output.summary), len(output.findings), output.risk_level)
            report = ReviewReport(
                summary=output.summary,
                risk_level=output.risk_level,
                stats=ReviewReportStats(
                    critical=0,
                    high=0,
                    medium=0,
                    low=0,
                    suggestion=0,
                ),
                changed_files=changed_files,
                changed_symbols=[],
                findings=output.findings,
                review_comment=output.review_comment,
            )
        else:
            logger.warning("[GRAPH] report_output is None, using FALLBACK branch | "
                           "summary_text=%s agent_results=%d aggregated_risk=%s",
                           state.summary_text[:60] if state.summary_text else "EMPTY",
                           len(state.agent_results),
                           "present" if state.aggregated_risk is not None else "None")
            # 降级：无 report output 时生成基础报告
            report = ReviewReport(
                summary=state.summary_text or f"PR 分析完成，共 {len(state.parsed_diff)} 个文件。",
                risk_level="LOW",
                stats=ReviewReportStats(),
                changed_files=changed_files,
                changed_symbols=[],
                findings=[],
                review_comment="## AI Review Summary\n\n基础分析完成。",
            )

        # 更新 stats（根据真实 findings 统计各级别数量）
        if state.aggregated_risk:
            for f in state.aggregated_risk.findings:
                level = f.level.upper()
                if level == "CRITICAL":
                    report.stats.critical += 1
                elif level == "HIGH":
                    report.stats.high += 1
                elif level in ("MEDIUM", "WARNING"):
                    report.stats.medium += 1
                elif level == "LOW":
                    report.stats.low += 1
                else:
                    report.stats.suggestion += 1
            logger.info("[GRAPH] Stats after aggregation | critical=%d high=%d medium=%d low=%d suggestion=%d",
                        report.stats.critical, report.stats.high, report.stats.medium,
                        report.stats.low, report.stats.suggestion)

        self._store.update_status(job_id, ReviewJobStatus.completed, report=report)
        logger.info("[GRAPH] Report saved to store | job=%s status=completed", job_id)
        self._add_progress(job_id, "DONE", 100, "Review 工作流已完成")

    def _add_progress(self, job_id: str, step: str, percent: int, message: str, event_type: str = "progress") -> None:
        self._store.add_progress_event(
            job_id,
            {"type": event_type, "step": step, "percent": percent, "message": message},
        )


async def _sync(fn, state: ReviewGraphState, github_client, store) -> ReviewGraphState:
    """将同步节点包装为协程。"""
    return fn(state, github_client, store)
