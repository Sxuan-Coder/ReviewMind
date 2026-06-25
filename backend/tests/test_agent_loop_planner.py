"""Tests for PlannerAgent：ReAct 循环产出审查计划。"""

from __future__ import annotations

import pytest

from app.agent_loop.planner import PlannerAgent
from app.agent_loop.schemas import ContextSnapshot, ReviewDimension


def _make_snapshot() -> ContextSnapshot:
    return ContextSnapshot(
        job_id="job-1",
        pr_url="https://github.com/o/r/pull/1",
        pr_info={"title": "Update docs", "author": "bob"},
        filtered_files={
            "included_files": [
                {"filename": "README.md", "status": "modified", "additions": 5, "deletions": 1},
            ]
        },
    )


class FakeLLMClient:
    """按预设队列返回文本的伪 LLM。"""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    async def chat(self, messages, *, model=None, temperature=0.1, **kwargs):  # noqa: ARG002
        if not self._responses:
            return "FINAL_ANSWER: {}"
        return self._responses.pop(0)


# ---------------------------------------------------------------------------
# 正常路径：LLM 直接给出最终计划（无需工具调用）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_planner_parses_minimal_plan():
    """LLM 直接产出只含 summary 的计划 → 正确解析。"""
    snap = _make_snapshot()
    fake = FakeLLMClient([
        'FINAL_ANSWER: {"dimensions": [{"dimension": "summary", "use_rag": false, '
        '"rationale": "仅文档改动"}], "overall_risk_hint": "LOW", "reasoning": "doc-only"}'
    ])
    planner = PlannerAgent(snap, client=fake, max_steps=3)
    plan = await planner.plan()
    assert [d.dimension for d in plan.dimensions] == [ReviewDimension.SUMMARY]
    assert plan.dimensions[0].rationale == "仅文档改动"
    assert plan.overall_risk_hint == "LOW"
    assert plan.reasoning == "doc-only"


@pytest.mark.asyncio
async def test_planner_parses_multi_dimension_plan():
    """LLM 产出多维度计划 → 全部解析。"""
    snap = _make_snapshot()
    fake = FakeLLMClient([
        'FINAL_ANSWER: ```json\n{"dimensions": ['
        '{"dimension": "summary"}, {"dimension": "security"}, {"dimension": "performance"}'
        '], "overall_risk_hint": "HIGH"}\n```'
    ])
    planner = PlannerAgent(snap, client=fake, max_steps=3)
    plan = await planner.plan()
    assert len(plan.dimensions) == 3
    assert plan.overall_risk_hint == "HIGH"


# ---------------------------------------------------------------------------
# 工具调用路径：LLM 先调工具再给最终计划
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_planner_executes_tool_then_finalizes():
    """LLM 先调 get_pr_overview，拿到观察后再产出计划。"""
    snap = _make_snapshot()
    fake = FakeLLMClient([
        '让我先看看 PR 概览。TOOL_CALL: {"name": "get_pr_overview", "arguments": {}}',
        'FINAL_ANSWER: {"dimensions": [{"dimension": "summary"}], "overall_risk_hint": "LOW"}',
    ])
    planner = PlannerAgent(snap, client=fake, max_steps=4)
    plan = await planner.plan()
    assert [d.dimension for d in plan.dimensions] == [ReviewDimension.SUMMARY]


# ---------------------------------------------------------------------------
# 降级路径
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_planner_fallback_on_max_steps():
    """LLM 一直调工具不终止 → 超步数降级为全维度计划。"""
    snap = _make_snapshot()
    # 每步都调工具，永不 FINAL
    fake = FakeLLMClient([
        'TOOL_CALL: {"name": "get_pr_overview", "arguments": {}}',
        'TOOL_CALL: {"name": "list_changed_files", "arguments": {}}',
        'TOOL_CALL: {"name": "detect_tech_stack", "arguments": {}}',
        'TOOL_CALL: {"name": "get_pr_overview", "arguments": {}}',
    ])
    planner = PlannerAgent(snap, client=fake, max_steps=4)
    plan = await planner.plan()
    # 降级计划应包含全部 4 个维度
    dims = {d.dimension for d in plan.dimensions}
    assert dims == {
        ReviewDimension.SUMMARY,
        ReviewDimension.SECURITY,
        ReviewDimension.PERFORMANCE,
        ReviewDimension.TEST,
    }
    assert "max_steps" in plan.reasoning


@pytest.mark.asyncio
async def test_planner_fallback_on_llm_failure():
    """LLM 客户端抛 LLMClientError → 降级为全维度计划。"""
    from app.core.llm import LLMClientError

    class FailClient:
        async def chat(self, *a, **k):  # noqa: ARG002
            raise LLMClientError("down")

    snap = _make_snapshot()
    planner = PlannerAgent(snap, client=FailClient(), max_steps=3)
    plan = await planner.plan()
    assert len(plan.dimensions) == 4
    assert "llm_unavailable" in plan.reasoning


@pytest.mark.asyncio
async def test_planner_fallback_on_unparseable_final():
    """LLM 输出无法解析的 FINAL_ANSWER → 多次重试后降级。"""
    snap = _make_snapshot()
    fake = FakeLLMClient([
        "FINAL_ANSWER: 这不是 JSON",  # 解析失败
        "FINAL_ANSWER: 仍然不是 json",  # 再失败
    ])
    planner = PlannerAgent(snap, client=fake, max_steps=3)
    plan = await planner.plan()
    # 重试用尽后，要么拿到兜底单 summary 计划（_parse_plan 内部兜底），要么 fallback
    # 这里 max_steps=3 且每次都 is_final，重试到步数用尽 → fallback_plan
    assert plan.dimensions  # 至少有一个维度


@pytest.mark.asyncio
async def test_planner_guarantees_summary_dimension():
    """解析出的计划若维度为空 → 至少保证 summary 维度（_parse_plan 内部兜底）。"""
    snap = _make_snapshot()
    fake = FakeLLMClient([
        'FINAL_ANSWER: {"dimensions": [], "overall_risk_hint": "LOW"}'
    ])
    planner = PlannerAgent(snap, client=fake, max_steps=3)
    plan = await planner.plan()
    assert ReviewDimension.SUMMARY in {d.dimension for d in plan.dimensions}
