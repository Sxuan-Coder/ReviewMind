"""Tests for agent_loop 基础原语：Tool 抽象、ToolRegistry、LLMDriver 解析。"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.agent_loop.llm_driver import AgentStep, LLMDriver
from app.agent_loop.tools import Tool, ToolCall, ToolRegistry, ToolResult


# ---------------------------------------------------------------------------
# 测试用 Tool 实现
# ---------------------------------------------------------------------------


class EchoArgs(BaseModel):
    text: str


class EchoTool(Tool[EchoArgs]):
    name = "echo"
    description = "回显输入文本"
    args_model = EchoArgs

    async def _run(self, args: EchoArgs) -> dict:
        return {"echoed": args.text}


class BoomTool(Tool[EchoArgs]):
    """总是抛异常的工具，用于测试异常兜底。"""

    name = "boom"
    description = "总是失败"
    args_model = EchoArgs

    async def _run(self, args: EchoArgs) -> dict:  # noqa: ARG002
        raise RuntimeError("intentional failure")


class FakeLLMClient:
    """伪 LLM 客户端：按预设队列返回文本。"""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[list[dict]] = []

    async def chat(self, messages, *, model=None, temperature=0.0, **kwargs):  # noqa: ARG002
        self.calls.append(messages)
        if not self._responses:
            return ""
        return self._responses.pop(0)


# ---------------------------------------------------------------------------
# Tool 抽象测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_invoke_success_returns_result():
    tool = EchoTool()
    result = await tool.invoke({"text": "hello"})
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.output == {"echoed": "hello"}
    assert result.error == ""


@pytest.mark.asyncio
async def test_tool_invoke_invalid_args_marks_failure():
    tool = EchoTool()
    # 缺少必填的 text 字段
    result = await tool.invoke({})
    assert result.success is False
    assert "invalid args" in result.error


@pytest.mark.asyncio
async def test_tool_invoke_exception_is_caught():
    tool = BoomTool()
    result = await tool.invoke({"text": "x"})
    assert result.success is False
    assert "intentional failure" in result.error


def test_tool_openai_schema_shape():
    tool = EchoTool()
    schema = tool.to_openai_schema()
    assert schema["type"] == "function"
    fn = schema["function"]
    assert fn["name"] == "echo"
    assert fn["description"] == "回显输入文本"
    # parameters 是 JSON Schema，应包含 text 字段
    assert "text" in fn["parameters"]["properties"]


def test_tool_result_llm_friendly_success_and_error():
    ok = ToolResult(name="echo", success=True, output={"k": 1})
    assert ok.to_llm_friendly().startswith("[tool:echo] OK")
    err = ToolResult(name="echo", success=False, error="boom")
    assert err.to_llm_friendly() == "[tool:echo] ERROR: boom"


# ---------------------------------------------------------------------------
# ToolRegistry 测试
# ---------------------------------------------------------------------------


def test_registry_register_and_get():
    reg = ToolRegistry()
    reg.register(EchoTool())
    assert reg.get("echo") is not None
    assert reg.get("nope") is None
    assert reg.names() == ["echo"]


def test_registry_rejects_duplicate_name():
    reg = ToolRegistry()
    reg.register(EchoTool())
    with pytest.raises(ValueError, match="already registered"):
        reg.register(EchoTool())


def test_registry_rejects_empty_name():
    class NoName(Tool[EchoArgs]):
        name = ""
        description = "x"
        args_model = EchoArgs

        async def _run(self, args):  # noqa: ARG002
            return {}

    reg = ToolRegistry()
    with pytest.raises(ValueError, match="non-empty name"):
        reg.register(NoName())


def test_registry_to_openai_schemas_lists_all():
    reg = ToolRegistry()
    reg.register(EchoTool())
    reg.register(BoomTool())
    schemas = reg.to_openai_schemas()
    names = {s["function"]["name"] for s in schemas}
    assert names == {"echo", "boom"}


# ---------------------------------------------------------------------------
# LLMDriver 解析测试
# ---------------------------------------------------------------------------


def _build_driver(responses: list[str]) -> tuple[LLMDriver, FakeLLMClient]:
    reg = ToolRegistry()
    reg.register(EchoTool())
    fake = FakeLLMClient(responses)
    driver = LLMDriver(reg, client=fake, max_steps=3)
    return driver, fake


@pytest.mark.asyncio
async def test_driver_parses_final_answer_tag():
    driver, _ = _build_driver(["FINAL_ANSWER: 只需要 summary 维度"])
    step = await driver.step([{"role": "user", "content": "q"}])
    assert step.is_final is True
    assert step.tool_call is None
    assert "summary 维度" in step.final_text


@pytest.mark.asyncio
async def test_driver_parses_tool_call_inline():
    driver, _ = _build_driver([
        '思考：先看文件。TOOL_CALL: {"name": "echo", "arguments": {"text": "go"}}'
    ])
    step = await driver.step([{"role": "user", "content": "q"}])
    assert step.is_final is False
    assert step.tool_call is not None
    assert step.tool_call.name == "echo"
    assert step.tool_call.arguments == {"text": "go"}


@pytest.mark.asyncio
async def test_driver_parses_tool_call_in_code_block():
    driver, _ = _build_driver([
        '分析中...\n```json\n{"name": "echo", "arguments": {"text": "x"}}\n```'
    ])
    step = await driver.step([{"role": "user", "content": "q"}])
    assert step.is_final is False
    assert step.tool_call is not None
    assert step.tool_call.name == "echo"


@pytest.mark.asyncio
async def test_driver_rejects_unregistered_tool():
    driver, _ = _build_driver(['TOOL_CALL: {"name": "nonexistent", "arguments": {}}'])
    step = await driver.step([{"role": "user", "content": "q"}])
    # 未知工具不应被解析为 tool_call → 退化为最终结果，保证 Loop 不发散
    assert step.is_final is True


@pytest.mark.asyncio
async def test_driver_empty_response_becomes_final():
    driver, _ = _build_driver([""])
    step = await driver.step([{"role": "user", "content": "q"}])
    assert step.is_final is True
    assert step.final_text == ""


@pytest.mark.asyncio
async def test_driver_plain_text_without_markers_treated_as_final():
    """没有 TOOL_CALL 也没有 FINAL_ANSWER 的纯文本 → 安全视为最终答案。"""
    driver, _ = _build_driver(["这就是我的结论，不需要再调工具。"])
    step = await driver.step([{"role": "user", "content": "q"}])
    assert step.is_final is True
    assert "结论" in step.final_text


@pytest.mark.asyncio
async def test_driver_llm_failure_propagates():
    """LLM 客户端抛 LLMClientError 时应向上抛，交由 Loop 降级。"""
    from app.core.llm import LLMClientError

    class FailClient:
        async def chat(self, *a, **k):  # noqa: ARG002
            raise LLMClientError("down")

    reg = ToolRegistry()
    reg.register(EchoTool())
    driver = LLMDriver(reg, client=FailClient(), max_steps=3)
    with pytest.raises(LLMClientError):
        await driver.step([{"role": "user", "content": "q"}])
