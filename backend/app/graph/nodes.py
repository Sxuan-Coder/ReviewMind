"""Review Graph 节点：每个节点读写 ReviewGraphState 的一部分。"""

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


def node_fetch_pr(state: ReviewGraphState, github_client: GitHubClient, store: ReviewJobStore) -> ReviewGraphState:
    """节点 1：解析 PR URL 并拉取 GitHub PR 基本信息。"""
    try:
        pr_ref = parse_github_pr_url(state.pr_url)
        import asyncio
        pr_info = asyncio.get_event_loop().run_until_complete(github_client.fetch_pull_request(pr_ref))
        state.pr_info = pr_info.model_dump(mode="json")
        store.save_pr_info(state.job_id, state.pr_info)
    except Exception as exc:
        state.error = f"FETCH_PR: {exc}"
    return state


async def node_fetch_pr_async(state: ReviewGraphState, github_client: GitHubClient, store: ReviewJobStore) -> ReviewGraphState:
    """节点 1（异步版）：解析 PR URL 并拉取 GitHub PR 基本信息。"""
    try:
        pr_ref = parse_github_pr_url(state.pr_url)
        pr_info = await github_client.fetch_pull_request(pr_ref)
        state.pr_info = pr_info.model_dump(mode="json")
        store.save_pr_info(state.job_id, state.pr_info)
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


def node_summary_agent(state: ReviewGraphState, _github_client: GitHubClient, _store: ReviewJobStore) -> ReviewGraphState:
    """节点 6：Summary Agent 生成总体摘要。"""
    if state.error:
        return state
    try:
        ctx = AgentContext(
            pr_info=state.pr_info,
            parsed_diff=state.parsed_diff,
            ast_contexts=state.ast_contexts,
        )
        result = summary_agent.run(ctx)
        state.summary_text = result.summary
        state.agent_results.append(result)
    except Exception as exc:
        state.warnings.append(f"SUMMARY_AGENT: {exc}")
        state.summary_text = f"PR 涉及 {len(state.parsed_diff)} 个文件变更。"
    return state


def node_security_agent(state: ReviewGraphState, _github_client: GitHubClient, _store: ReviewJobStore) -> ReviewGraphState:
    """节点 7：Security Agent。"""
    if state.error:
        return state
    try:
        ctx = AgentContext(
            pr_info=state.pr_info,
            parsed_diff=state.parsed_diff,
            ast_contexts=state.ast_contexts,
        )
        result = security_agent.run(ctx)
        state.agent_results.append(result)
    except Exception as exc:
        state.warnings.append(f"SECURITY_AGENT: {exc}")
    return state


def node_performance_agent(state: ReviewGraphState, _github_client: GitHubClient, _store: ReviewJobStore) -> ReviewGraphState:
    """节点 8：Performance Agent。"""
    if state.error:
        return state
    try:
        ctx = AgentContext(
            pr_info=state.pr_info,
            parsed_diff=state.parsed_diff,
            ast_contexts=state.ast_contexts,
        )
        result = performance_agent.run(ctx)
        state.agent_results.append(result)
    except Exception as exc:
        state.warnings.append(f"PERFORMANCE_AGENT: {exc}")
    return state


def node_test_agent(state: ReviewGraphState, _github_client: GitHubClient, _store: ReviewJobStore) -> ReviewGraphState:
    """节点 9：Test Agent。"""
    if state.error:
        return state
    try:
        ctx = AgentContext(
            pr_info=state.pr_info,
            parsed_diff=state.parsed_diff,
            ast_contexts=state.ast_contexts,
        )
        result = test_agent.run(ctx)
        state.agent_results.append(result)
    except Exception as exc:
        state.warnings.append(f"TEST_AGENT: {exc}")
    return state


def node_risk_judge(state: ReviewGraphState, _github_client: GitHubClient, _store: ReviewJobStore) -> ReviewGraphState:
    """节点 10：Risk Judge 聚合所有 agent findings。"""
    if state.error:
        return state
    try:
        state.aggregated_risk = risk_judge_agent.aggregate(state.agent_results)
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