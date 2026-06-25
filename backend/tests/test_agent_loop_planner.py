"""Tests for PlannerAgent：原生 Function Calling ReAct 循环产出审查计划。"""

from __future__ import annotations

import pytest

from app.agent_loop.planner import PlannerAgent
from app.agent_loop.schemas import ContextSnapshot, ReviewDimension
from app.core.llm import ToolCallItem, ToolCallResponse


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
    """伪 LLM：按队列返回原生 ToolCallResponse。"""

    def __init__(self, responses: list[ToolCallResponse]) -> None:
        self._responses = list(responses)

    async def chat_with_tools(self, messages, *, tools, model=None, temperature=0.1, tool_choice="auto"):  # noqa: ARG002
        if not self._responses:
            return ToolCallResponse(content="{}", tool_calls=[], finish_reason="stop")
        return self._responses.pop(0)


def _tool_call_resp(name, arguments=None, call_id="call_1") -> ToolCallResponse:
    return ToolCallResponse(
        content=None,
        tool_calls=[ToolCallItem(id=call_id, name=name, arguments=arguments or {})],
        finish_reason="tool_calls",
    )


def _final_resp(text: str) -> ToolCallResponse:
    return ToolCallResponse(content=text, tool_calls=[], finish_reason="stop")


# ---------------------------------------------------------------------------
# 正常路径：LLM 直接给出最终计划（无工具调用）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_planner_parses_minimal_plan():
    """LLM 直接产出只含 summary 的计划 → 正确解析。"""
    snap = _make_snapshot()
    fake = FakeLLMClient([
        _final_resp('{"dimensions": [{"dimension": "summary", "use_rag": false, '
        '"rationale": "仅文档改动"}], "overall_risk_hint": "LOW", "reasoning": "doc-only"}')
    ])
    planner = PlannerAgent(snap, client=fake, max_steps=3)
    plan = await planner.plan()
    assert [d.dimension for d in plan.dimensions] == [ReviewDimension.SUMMARY]
    assert plan.dimensions[0].rationale == "仅文档改动"
    assert plan.overall_risk_hint == "LOW"
    assert plan.reasoning == "doc-only"


@pytest.mark.asyncio
async def test_planner_parses_plan_from_markdown_block():
    """LLM 把 JSON 包在代码块里 → 仍能解析。"""
    snap = _make_snapshot()
    fake = FakeLLMClient([
        _final_resp('```json\n{"dimensions": ['
        '{"dimension": "summary"}, {"dimension": "security"}, {"dimension": "performance"}'
        '], "overall_risk_hint": "HIGH"}\n```')
    ])
    planner = PlannerAgent(snap, client=fake, max_steps=3)
    plan = await planner.plan()
    assert len(plan.dimensions) == 3
    assert plan.overall_risk_hint == "HIGH"


# ---------------------------------------------------------------------------
# 工具调用路径：LLM 先用原生 tool_calls 调工具，再给最终计划
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_planner_executes_tool_then_finalizes():
    """LLM 先调 get_pr_overview（原生 tool_calls），拿到观察后再产出计划。"""
    snap = _make_snapshot()
    fake = FakeLLMClient([
        _tool_call_resp("get_pr_overview", {}, call_id="call_overview"),
        _final_resp('{"dimensions": [{"dimension": "summary"}], "overall_risk_hint": "LOW"}'),
    ])
    planner = PlannerAgent(snap, client=fake, max_steps=4)
    plan = await planner.plan()
    assert [d.dimension for d in plan.dimensions] == [ReviewDimension.SUMMARY]


@pytest.mark.asyncio
async def test_planner_multi_turn_tool_calls():
    """LLM 连续调用多个工具，每次都正确回灌 tool_call_id。"""
    snap = _make_snapshot()
    fake = FakeLLMClient([
        _tool_call_resp("get_pr_overview", {}, call_id="c1"),
        _tool_call_resp("list_changed_files", {}, call_id="c2"),
        _final_resp('{"dimensions": [{"dimension": "summary"},{"dimension": "security"}], '
                    '"overall_risk_hint": "MEDIUM"}'),
    ])
    planner = PlannerAgent(snap, client=fake, max_steps=6)
    plan = await planner.plan()
    dims = {d.dimension for d in plan.dimensions}
    assert ReviewDimension.SUMMARY in dims
    assert ReviewDimension.SECURITY in dims


# ---------------------------------------------------------------------------
# 降级路径
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_planner_fallback_on_max_steps():
    """LLM 一直调工具不终止 → 超步数降级为全维度计划。"""
    snap = _make_snapshot()
    # 每步都调工具，永不给最终文本
    fake = FakeLLMClient([
        _tool_call_resp("get_pr_overview", {}, call_id=f"c{i}")
        for i in range(4)
    ])
    planner = PlannerAgent(snap, client=fake, max_steps=4)
    plan = await planner.plan()
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
        async def chat_with_tools(self, *a, **k):  # noqa: ARG002
            raise LLMClientError("down")

    snap = _make_snapshot()
    planner = PlannerAgent(snap, client=FailClient(), max_steps=3)
    plan = await planner.plan()
    assert len(plan.dimensions) == 4
    assert "llm_unavailable" in plan.reasoning


@pytest.mark.asyncio
async def test_planner_fallback_on_unparseable_final():
    """LLM 最终文本无法解析为 JSON → 多次重试后降级。"""
    snap = _make_snapshot()
    fake = FakeLLMClient([
        _final_resp("这不是 JSON"),
        _final_resp("仍然不是 json"),
    ])
    planner = PlannerAgent(snap, client=fake, max_steps=3)
    plan = await planner.plan()
    assert plan.dimensions  # 至少有一个维度


@pytest.mark.asyncio
async def test_planner_guarantees_summary_dimension():
    """解析出的计划若维度为空 → 至少保证 summary 维度（_parse_plan 内部兜底）。"""
    snap = _make_snapshot()
    fake = FakeLLMClient([
        _final_resp('{"dimensions": [], "overall_risk_hint": "LOW"}')
    ])
    planner = PlannerAgent(snap, client=fake, max_steps=3)
    plan = await planner.plan()
    assert ReviewDimension.SUMMARY in {d.dimension for d in plan.dimensions}
