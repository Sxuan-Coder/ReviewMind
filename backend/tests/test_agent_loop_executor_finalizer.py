"""Tests for Executor 与 Finalizer。"""

from __future__ import annotations

import pytest

from app.agent_loop.executor import Executor
from app.agent_loop.finalizer import Finalizer
from app.agent_loop.schemas import (
    ContextSnapshot,
    DimensionResult,
    DimensionTask,
    ReviewDimension,
    ReviewPlan,
)
from app.schemas.agents import AgentFindingsResult
from app.schemas.review import ReviewFinding


def _make_snapshot() -> ContextSnapshot:
    return ContextSnapshot(
        job_id="job-1",
        pr_url="https://github.com/o/r/pull/1",
        pr_info={"title": "T", "author": "a"},
        filtered_files={"included_files": [{"filename": "x.py", "additions": 1, "deletions": 0}]},
        parsed_diff=[{"file": "x.py", "changed_lines": [1]}],
        tech_stack_prompt="前端使用 React，JSX 渲染自动转义 HTML",
    )


def _finding(agent="security_agent", file="x.py", ftype="sql_injection", level="HIGH"):
    return ReviewFinding(
        id="f1", agent=agent, file=file, line=1, level=level,
        type=ftype, confidence=0.8, description="d", suggestion="s",
    )


# ---------------------------------------------------------------------------
# Executor 测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_runs_planned_dimensions(monkeypatch):
    """Executor 按 plan 中的维度调用对应 agent。"""
    snap = _make_snapshot()
    called: list[str] = []

    async def fake_run_async(ctx):  # noqa: ARG001
        # 根据被调用的模块名区分维度
        return AgentFindingsResult(agent="x", summary="", findings=[])

    # 让 4 个 agent 模块共用一个 fake，但记录调用
    for mod_name in ("summary_agent", "security_agent", "performance_agent", "test_agent"):
        async def _stub(ctx, _name=mod_name):
            called.append(_name)
            return AgentFindingsResult(agent=_name, summary="", findings=[])
        monkeypatch.setattr(f"app.agents.{mod_name}.run_async", _stub)

    plan = ReviewPlan(dimensions=[
        DimensionTask(dimension=ReviewDimension.SUMMARY),
        DimensionTask(dimension=ReviewDimension.SECURITY),
    ])
    executor = Executor(snap)
    results = await executor.execute(plan)
    assert len(results) == 2
    assert all(r.success for r in results)
    assert set(called) == {"summary_agent", "security_agent"}


@pytest.mark.asyncio
async def test_executor_parallelism_preserved(monkeypatch):
    """多个维度应被并行执行（通过计数并发来验证）。"""
    snap = _make_snapshot()
    import asyncio as _asyncio

    current = {"n": 0, "max": 0}

    async def fake_run_async(ctx):  # noqa: ARG001
        current["n"] += 1
        current["max"] = max(current["max"], current["n"])
        await _asyncio.sleep(0.05)
        current["n"] -= 1
        return AgentFindingsResult(agent="x", summary="", findings=[])

    for mod_name in ("summary_agent", "security_agent", "performance_agent", "test_agent"):
        monkeypatch.setattr(f"app.agents.{mod_name}.run_async", fake_run_async)

    plan = ReviewPlan(dimensions=[DimensionTask(dimension=d) for d in ReviewDimension])
    executor = Executor(snap)
    await executor.execute(plan)
    # 4 个维度并行 → 最大并发应 >= 2（并行生效的证据）
    assert current["max"] >= 2


@pytest.mark.asyncio
async def test_executor_empty_plan_returns_empty():
    snap = _make_snapshot()
    executor = Executor(snap)
    results = await executor.execute(ReviewPlan(dimensions=[]))
    assert results == []


@pytest.mark.asyncio
async def test_executor_agent_failure_isolated(monkeypatch):
    """单个维度 agent 抛异常不应影响其他维度。"""
    snap = _make_snapshot()

    async def boom(ctx):  # noqa: ARG001
        raise RuntimeError("agent down")

    async def ok(ctx):  # noqa: ARG001
        return AgentFindingsResult(agent="summary_agent", summary="ok", findings=[])

    monkeypatch.setattr("app.agents.security_agent.run_async", boom)
    monkeypatch.setattr("app.agents.summary_agent.run_async", ok)

    plan = ReviewPlan(dimensions=[
        DimensionTask(dimension=ReviewDimension.SECURITY),
        DimensionTask(dimension=ReviewDimension.SUMMARY),
    ])
    executor = Executor(snap)
    results = await executor.execute(plan)
    by_dim = {r.dimension: r for r in results}
    # security 失败但 summary 成功 —— 故障被隔离
    assert by_dim[ReviewDimension.SUMMARY].success is True
    # security 的 tool 内部捕获了异常，标记为失败
    assert by_dim[ReviewDimension.SECURITY].success is False


# ---------------------------------------------------------------------------
# Finalizer 测试
# ---------------------------------------------------------------------------


def test_finalizer_aggregates_and_generates_report():
    snap = _make_snapshot()
    dim_results = [
        DimensionResult(
            dimension=ReviewDimension.SUMMARY,
            result=AgentFindingsResult(agent="summary_agent", summary="PR 摘要", findings=[]),
        ),
        DimensionResult(
            dimension=ReviewDimension.SECURITY,
            result=AgentFindingsResult(
                agent="security_agent",
                findings=[_finding(level="HIGH")],
            ),
        ),
    ]
    finalizer = Finalizer(snap)
    report = finalizer.finalize(dim_results, job_id="job-1")

    assert report.summary_text == "PR 摘要"
    assert len(report.aggregated_risk.findings) == 1
    assert report.aggregated_risk.risk_level == "HIGH"
    assert "PR 摘要" in report.report_output.review_comment


def test_finalizer_filters_false_positives():
    """React 技术栈下 .tsx 的 XSS finding 应被过滤。"""
    snap = _make_snapshot()  # tech_stack 含 React
    fp_finding = ReviewFinding(
        id="f", agent="security_agent", file="App.tsx", line=1, level="HIGH",
        type="xss", confidence=0.8, description="d", suggestion="s",
    )
    dim_results = [
        DimensionResult(
            dimension=ReviewDimension.SECURITY,
            result=AgentFindingsResult(
                agent="security_agent", findings=[fp_finding],
            ),
        ),
    ]
    finalizer = Finalizer(snap)
    report = finalizer.finalize(dim_results, job_id="job-1")
    assert report.findings_dropped == 1
    assert len(report.aggregated_risk.findings) == 0


def test_finalizer_keeps_non_false_positive():
    snap = _make_snapshot()
    dim_results = [
        DimensionResult(
            dimension=ReviewDimension.SECURITY,
            result=AgentFindingsResult(
                agent="security_agent", findings=[_finding(ftype="sql_injection", file="db.py")],
            ),
        ),
    ]
    finalizer = Finalizer(snap)
    report = finalizer.finalize(dim_results, job_id="job-1")
    assert report.findings_dropped == 0
    assert len(report.aggregated_risk.findings) == 1


def test_finalizer_default_summary_when_missing():
    """无 summary 维度时，使用兜底摘要。"""
    snap = _make_snapshot()
    snap.parsed_diff = [{"file": "a.py"}, {"file": "b.py"}]
    dim_results = [
        DimensionResult(
            dimension=ReviewDimension.SECURITY,
            result=AgentFindingsResult(agent="security_agent", findings=[]),
        ),
    ]
    finalizer = Finalizer(snap)
    report = finalizer.finalize(dim_results, job_id="job-1")
    assert "2 个文件" in report.summary_text


def test_finalizer_handles_empty_results():
    """所有维度都没有 result 时也能产出报告。"""
    snap = _make_snapshot()
    finalizer = Finalizer(snap)
    report = finalizer.finalize([], job_id="job-1")
    assert report.aggregated_risk.risk_level == "LOW"
    assert len(report.aggregated_risk.findings) == 0
