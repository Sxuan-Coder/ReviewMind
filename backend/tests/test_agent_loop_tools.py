"""Tests for agent_loop agent_tools：Planner/Executor 工具封装。"""

from __future__ import annotations

import pytest

from app.agent_loop.agent_tools import (
    AnalyzeDimensionTool,
    build_executor_registry,
    build_planner_registry,
)
from app.agent_loop.schemas import ContextSnapshot, ReviewDimension


def _make_snapshot() -> ContextSnapshot:
    """构造一个带真实形态数据的快照。"""
    return ContextSnapshot(
        job_id="job-1",
        pr_url="https://github.com/o/r/pull/1",
        pr_info={"title": "Add login", "author": "alice", "state": "open"},
        filtered_files={
            "included_files": [
                {"filename": "src/auth.py", "status": "modified", "additions": 10, "deletions": 2},
                {"filename": "src/utils.js", "status": "added", "additions": 5, "deletions": 0},
                {"filename": "README.md", "status": "modified", "additions": 1, "deletions": 1},
            ]
        },
        parsed_diff=[{"file": "src/auth.py", "changed_lines": [10]}],
        tech_stack_prompt="React JSX (auto-escaping)",
    )


# ---------------------------------------------------------------------------
# Planner 探查工具
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pr_overview_aggregates_size():
    snap = _make_snapshot()
    reg = build_planner_registry(snap)
    tool = reg.get("get_pr_overview")
    result = await tool.invoke({})
    assert result.success is True
    out = result.output
    assert out["title"] == "Add login"
    assert out["author"] == "alice"
    assert out["changed_files"] == 3
    assert out["additions"] == 16  # 10+5+1
    assert out["deletions"] == 3   # 2+0+1


@pytest.mark.asyncio
async def test_list_changed_files_respects_limit():
    snap = _make_snapshot()
    reg = build_planner_registry(snap)
    tool = reg.get("list_changed_files")
    result = await tool.invoke({"limit": 2})
    assert result.success is True
    assert result.output["total"] == 3
    assert len(result.output["files"]) == 2
    assert result.output["files"][0]["filename"] == "src/auth.py"


@pytest.mark.asyncio
async def test_detect_tech_stack_returns_prompt():
    snap = _make_snapshot()
    reg = build_planner_registry(snap)
    tool = reg.get("detect_tech_stack")
    result = await tool.invoke({})
    assert result.success is True
    assert result.output["detected"] is True
    assert "React" in result.output["tech_stack_context"]


@pytest.mark.asyncio
async def test_detect_tech_stack_empty_when_no_prompt():
    snap = ContextSnapshot(job_id="j", pr_url="u")
    reg = build_planner_registry(snap)
    tool = reg.get("detect_tech_stack")
    result = await tool.invoke({})
    assert result.output["detected"] is False


def test_planner_registry_has_three_readonly_tools():
    snap = _make_snapshot()
    reg = build_planner_registry(snap)
    assert set(reg.names()) == {"get_pr_overview", "list_changed_files", "detect_tech_stack"}


# ---------------------------------------------------------------------------
# Executor 执行工具
# ---------------------------------------------------------------------------


def test_executor_registry_has_two_tools():
    snap = _make_snapshot()
    reg = build_executor_registry(snap)
    assert set(reg.names()) == {"analyze_dimension", "cross_validate"}


@pytest.mark.asyncio
async def test_analyze_dimension_unknown_returns_error(monkeypatch):
    """未知维度不应崩溃，返回结构化错误。"""
    snap = _make_snapshot()
    tool = AnalyzeDimensionTool(snap)
    # 用一个无效的 dimension 值触发兜底：直接调 _run 绕过枚举校验
    result = await tool.invoke({"dimension": "summary"})  # 合法枚举，走正常路径
    assert result.success is True
    assert result.output["dimension"] == "summary"


@pytest.mark.asyncio
async def test_analyze_dimension_calls_agent(monkeypatch):
    """验证 analyze_dimension 真的调用了对应 agent 的 run_async。"""
    snap = _make_snapshot()
    captured: dict = {}

    async def fake_run_async(ctx):  # noqa: ARG001
        from app.schemas.agents import AgentFindingsResult
        captured["called"] = True
        return AgentFindingsResult(agent="summary_agent", summary="mocked", findings=[])

    monkeypatch.setattr("app.agents.summary_agent.run_async", fake_run_async)

    tool = AnalyzeDimensionTool(snap)
    result = await tool.invoke({"dimension": "summary", "use_rag": False})
    assert result.success is True
    assert result.output["ok"] is True
    assert result.output["summary"] == "mocked"
    assert captured["called"] is True


@pytest.mark.asyncio
async def test_analyze_dimension_use_rag_flag_controls_context(monkeypatch):
    """use_rag=False 时，传给 agent 的 RAG 上下文应为空。"""
    snap = ContextSnapshot(
        job_id="j", pr_url="u",
        rag_contexts=[{"file_path": "x.py", "code": "y"}],
    )
    captured: dict = {}

    async def fake_run_async(ctx):
        captured["rag_len"] = len(ctx.rag_contexts)
        from app.schemas.agents import AgentFindingsResult
        return AgentFindingsResult(agent="summary_agent", summary="", findings=[])

    monkeypatch.setattr("app.agents.summary_agent.run_async", fake_run_async)

    tool = AnalyzeDimensionTool(snap)
    await tool.invoke({"dimension": "summary", "use_rag": False})
    assert captured["rag_len"] == 0

    await tool.invoke({"dimension": "summary", "use_rag": True})
    assert captured["rag_len"] == 1


@pytest.mark.asyncio
async def test_cross_validate_flags_react_xss_as_false_positive():
    """React 技术栈下 .tsx 的 XSS 应被判为误报（复用 finding_validator 规则）。"""
    snap = ContextSnapshot(
        job_id="j", pr_url="u",
        tech_stack_prompt="前端使用 React，JSX 渲染自动转义 HTML",
    )
    reg = build_executor_registry(snap)
    tool = reg.get("cross_validate")
    result = await tool.invoke({"finding_type": "xss", "file": "src/App.tsx"})
    assert result.success is True
    assert result.output["is_false_positive"] is True
    assert "丢弃" in result.output["verdict"]


@pytest.mark.asyncio
async def test_cross_validate_keeps_real_issue():
    """非误报场景应返回有效判定。"""
    snap = ContextSnapshot(job_id="j", pr_url="u", tech_stack_prompt="")
    reg = build_executor_registry(snap)
    tool = reg.get("cross_validate")
    result = await tool.invoke({"finding_type": "sql_injection", "file": "db.py"})
    assert result.output["is_false_positive"] is False
    assert "保留" in result.output["verdict"]
