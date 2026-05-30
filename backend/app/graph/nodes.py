"""Review Graph 节点：每个节点读写 ReviewGraphState 的一部分。"""

import asyncio
from typing import Any, Callable, Coroutine

from app.agents import (
    performance_agent,
    report_agent,
    risk_judge_agent,
    security_agent,
    summary_agent,
    test_agent,
)
from app.graph.state import ReviewGraphState
from app.schemas.agents import AgentContext
from app.schemas.ast_context import AstContext
from app.schemas.diff import PullRequestFile
from app.schemas.github import GitHubPullRequestFile
from app.services.ast_context import extract_ast_context
from app.services.diff_filter import filter_diff_files
from app.services.diff_parser import parse_diff_file
from app.services.github_client import GitHubClient
from app.services.github_url_parser import parse_github_pr_url
from app.services.review_job_store import ReviewJobStore


def _run_async(coro: Callable[..., Coroutine], *args, **kwargs) -> Any:
    """在同步上下文中安全地执行异步函数。"""
    result_holder: list[Any] = []
    exception_holder: list[Exception] = []

    async def _runner() -> None:
        try:
            result_holder.append(await coro(*args, **kwargs))
        except Exception as exc:
            exception_holder.append(exc)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        # 已在事件循环中，创建 task 并等待
        import concurrent.futures
        future = asyncio.run_coroutine_threadsafe(_runner(), loop)
        future.result(timeout=120)
    else:
        loop.run_until_complete(_runner())

    if exception_holder:
        raise exception_holder[0]
    return result_holder[0] if result_holder else None


async def node_fetch_pr(state: ReviewGraphState, github_client: GitHubClient, store: ReviewJobStore) -> ReviewGraphState:
    """节点 1：解析 PR URL 并拉取 GitHub PR 基本信息。"""
    try:
        pr_ref = parse_github_pr_url(state.pr_url)
        pr_info = await github_client.fetch_pull_request(pr_ref)
        state.pr_info = pr_info.model_dump(mode="json")
        await store.save_pr_info(state.job_id, state.pr_info)
    except Exception as exc:
        state.error = f"FETCH_PR: {exc}"
    return state


async def node_fetch_pr_async(state: ReviewGraphState, github_client: GitHubClient, store: ReviewJobStore) -> ReviewGraphState:
    """节点 1（异步版）：解析 PR URL 并拉取 GitHub PR 基本信息。"""
    try:
        pr_ref = parse_github_pr_url(state.pr_url)
        pr_info = await github_client.fetch_pull_request(pr_ref)
        state.pr_info = pr_info.model_dump(mode="json")
        await store.save_pr_info(state.job_id, state.pr_info)
    except Exception as exc:
        state.error = f"FETCH_PR: {exc}"
    return state


async def node_fetch_files_async(state: ReviewGraphState, github_client: GitHubClient, _store: ReviewJobStore) -> ReviewGraphState:
    """节点 2：拉取 PR changed files。"""
    if state.error:
        return state
    try:
        pr_ref = parse_github_pr_url(state.pr_url)
        files = await github_client.fetch_pull_request_files(pr_ref)
        state.github_files = [f.model_dump(mode="json") for f in files]
    except Exception as exc:
        state.error = f"FETCH_FILES: {exc}"
    return state


def node_diff_filter(state: ReviewGraphState, _github_client: GitHubClient, _store: ReviewJobStore) -> ReviewGraphState:
    """节点 3：过滤无意义的 diff 文件。"""
    if state.error:
        return state
    try:
        pull_request_files = [
            PullRequestFile(
                filename=f["filename"],
                status=f["status"],
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
                patch=f.get("patch"),
            )
            for f in state.github_files
        ]
        filtered = filter_diff_files(pull_request_files)
        state.filtered_files = filtered.model_dump(mode="json")
    except Exception as exc:
        state.error = f"DIFF_FILTER: {exc}"
    return state


def node_parse_diff(state: ReviewGraphState, _github_client: GitHubClient, _store: ReviewJobStore) -> ReviewGraphState:
    """节点 4：解析每个 included file 的 patch 为结构化 hunks 和 changed lines。"""
    if state.error:
        return state
    try:
        included = state.filtered_files.get("included_files", [])
        parsed = []
        for f in included:
            pf = PullRequestFile(
                filename=f["filename"],
                status=f["status"],
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
                patch=f.get("patch"),
            )
            parsed.append(parse_diff_file(pf).model_dump(mode="json"))
        state.parsed_diff = parsed
    except Exception as exc:
        state.error = f"DIFF_PARSE: {exc}"
    return state


def node_ast_context(state: ReviewGraphState, _github_client: GitHubClient, _store: ReviewJobStore) -> ReviewGraphState:
    """节点 5：对 Python 文件提取 AST 上下文。非关键节点，失败降级。"""
    if state.error:
        return state
    try:
        contexts: list[dict] = []
        included = state.filtered_files.get("included_files", [])
        file_map = {f["filename"]: f for f in included}
        for diff in state.parsed_diff:
            filename = diff.get("file", "")
            changed_lines = diff.get("changed_lines", [])
            f_info = file_map.get(filename, {})
            patch = f_info.get("patch", "")
            if not patch or not changed_lines:
                continue
            # 尝试从 patch 还原源码（仅限新增文件或小 diff 的降级方案）
            source = _extract_source_from_patch(patch)
            if source:
                try:
                    ctx_list = extract_ast_context(filename, source, changed_lines)
                    contexts.extend([c.model_dump(mode="json") for c in ctx_list])
                except Exception:
                    pass  # AST 解析失败降级
        state.ast_contexts = contexts
    except Exception as exc:
        state.warnings.append(f"AST_CONTEXT: {exc}")
    return state


async def node_summary_agent(state: ReviewGraphState, _github_client: GitHubClient, _store: ReviewJobStore) -> ReviewGraphState:
    """节点 6：Summary Agent 生成总体摘要（调用 LLM）。"""
    if state.error:
        return state
    try:
        ctx = AgentContext(
            pr_info=state.pr_info,
            parsed_diff=state.parsed_diff,
            ast_contexts=state.ast_contexts,
        )
        result = await summary_agent.run_async(ctx)
        state.summary_text = result.summary
        state.agent_results.append(result)
        # SSE 推送摘要文本流
        if result.summary:
            await _store.add_progress_event(
                state.job_id,
                {"type": "chunk", "target": "summary", "content": result.summary},
            )
    except Exception as exc:
        try:
            result = summary_agent.run(ctx)
            state.summary_text = result.summary
            state.agent_results.append(result)
        except Exception:
            pass
        state.warnings.append(f"SUMMARY_AGENT: {exc}")
        if not state.summary_text:
            state.summary_text = f"PR 涉及 {len(state.parsed_diff)} 个文件变更。"
    return state


async def node_security_agent(state: ReviewGraphState, _github_client: GitHubClient, _store: ReviewJobStore) -> ReviewGraphState:
    """节点 7：Security Agent（调用 LLM 分析安全风险）。"""
    if state.error:
        return state
    try:
        ctx = AgentContext(
            pr_info=state.pr_info,
            parsed_diff=state.parsed_diff,
            ast_contexts=state.ast_contexts,
        )
        result = await security_agent.run_async(ctx)
        state.agent_results.append(result)
        # SSE 推送 finding 事件（"type":"finding" 放最后，避免被 f.type 覆盖）
        for f in result.findings:
            await _store.add_progress_event(
                state.job_id,
                {
                    "id": f.id, "agent": f.agent, "file": f.file, "line": f.line,
                    "symbol": f.symbol or "", "level": f.level, "finding_type": f.type,
                    "confidence": f.confidence, "description": f.description,
                    "suggestion": f.suggestion, "type": "finding",
                },
            )
    except Exception as exc:
        try:
            result = security_agent.run(ctx)
            state.agent_results.append(result)
        except Exception:
            pass
        state.warnings.append(f"SECURITY_AGENT: {exc}")
    return state


async def node_performance_agent(state: ReviewGraphState, _github_client: GitHubClient, _store: ReviewJobStore) -> ReviewGraphState:
    """节点 8：Performance Agent（调用 LLM 分析性能风险）。"""
    if state.error:
        return state
    try:
        ctx = AgentContext(
            pr_info=state.pr_info,
            parsed_diff=state.parsed_diff,
            ast_contexts=state.ast_contexts,
        )
        result = await performance_agent.run_async(ctx)
        state.agent_results.append(result)
        for f in result.findings:
            await _store.add_progress_event(
                state.job_id,
                {
                    "id": f.id, "agent": f.agent, "file": f.file, "line": f.line,
                    "symbol": f.symbol or "", "level": f.level, "finding_type": f.type,
                    "confidence": f.confidence, "description": f.description,
                    "suggestion": f.suggestion, "type": "finding",
                },
            )
    except Exception as exc:
        try:
            result = performance_agent.run(ctx)
            state.agent_results.append(result)
        except Exception:
            pass
        state.warnings.append(f"PERFORMANCE_AGENT: {exc}")
    return state


async def node_test_agent(state: ReviewGraphState, _github_client: GitHubClient, _store: ReviewJobStore) -> ReviewGraphState:
    """节点 9：Test Agent（调用 LLM 分析测试覆盖）。"""
    if state.error:
        return state
    try:
        ctx = AgentContext(
            pr_info=state.pr_info,
            parsed_diff=state.parsed_diff,
            ast_contexts=state.ast_contexts,
        )
        result = await test_agent.run_async(ctx)
        state.agent_results.append(result)
        for f in result.findings:
            await _store.add_progress_event(
                state.job_id,
                {
                    "id": f.id, "agent": f.agent, "file": f.file, "line": f.line,
                    "symbol": f.symbol or "", "level": f.level, "finding_type": f.type,
                    "confidence": f.confidence, "description": f.description,
                    "suggestion": f.suggestion, "type": "finding",
                },
            )
    except Exception as exc:
        try:
            result = test_agent.run(ctx)
            state.agent_results.append(result)
        except Exception:
            pass
        state.warnings.append(f"TEST_AGENT: {exc}")
    return state


async def node_risk_judge(state: ReviewGraphState, _github_client: GitHubClient, _store: ReviewJobStore) -> ReviewGraphState:
    """节点 10：Risk Judge 聚合所有 agent findings。"""
    if state.error:
        return state
    try:
        state.aggregated_risk = risk_judge_agent.aggregate(state.agent_results)
        # SSE 推送最终风险统计
        if state.aggregated_risk:
            await _store.add_progress_event(
                state.job_id,
                {
                    "type": "chunk", "target": "report",
                    "content": f"Risk Judge 完成：{len(state.aggregated_risk.findings)} 个风险，去重 {state.aggregated_risk.dedup_count} 个，风险等级 {state.aggregated_risk.risk_level}",
                },
            )
    except Exception as exc:
        state.warnings.append(f"RISK_JUDGE: {exc}")
    return state


def node_report_agent(state: ReviewGraphState, _github_client: GitHubClient, _store: ReviewJobStore) -> ReviewGraphState:
    """节点 11：Report Agent 生成最终报告。"""
    if state.error:
        return state
    try:
        if state.aggregated_risk is None:
            return state
        state.report_output = report_agent.generate_report(
            state.job_id,
            state.aggregated_risk,
            state.summary_text,
        )
    except Exception as exc:
        state.warnings.append(f"REPORT_AGENT: {exc}")
    return state


def _extract_source_from_patch(patch: str) -> str | None:
    """尝试从 patch 中提取全部 "+" 行作为源码的近似值（降级方案）。"""
    lines = []
    for line in patch.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
        elif not line.startswith("-") and not line.startswith("@@") and not line.startswith("---"):
            lines.append(line)
    return "\n".join(lines) if lines else None