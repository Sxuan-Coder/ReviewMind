"""Tests for agent_loop 基础原语：Tool 抽象、ToolRegistry、LLMDriver 解析。"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.agent_loop.llm_driver import AgentStep, LLMDriver
from app.agent_loop.tools import Tool, ToolCall, ToolRegistry, ToolResult
from app.core.llm import ToolCallItem, ToolCallResponse


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
    """伪 LLM 客户端：支持原生 chat_with_tools 协议。

    responses 是 ToolCallResponse 队列；按调用顺序逐个弹出。
    """

    def __init__(self, responses: list[ToolCallResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[list[dict]] = []

    async def chat_with_tools(self, messages, *, tools, model=None, temperature=0.0, tool_choice="auto"):  # noqa: ARG002
        self.calls.append(messages)
        if not self._responses:
            return ToolCallResponse(content="", tool_calls=[], finish_reason="stop")
        return self._responses.pop(0)

    async def chat(self, messages, *, model=None, temperature=0.0, **kwargs):  # noqa: ARG002
        # 兼容：driver 现在用 chat_with_tools，这里不会被调用
        return ""


def _tool_call_response(name="echo", arguments=None, call_id="call_test") -> ToolCallResponse:
    """便捷构造一个原生 tool_calls 响应。"""
    return ToolCallResponse(
        content=None,
        tool_calls=[ToolCallItem(id=call_id, name=name, arguments=arguments or {})],
        finish_reason="tool_calls",
    )


def _final_response(text: str) -> ToolCallResponse:
    """便捷构造一个最终文本响应（无 tool_calls）。"""
    return ToolCallResponse(content=text, tool_calls=[], finish_reason="stop")


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


def _build_driver(responses: list[ToolCallResponse]) -> tuple[LLMDriver, FakeLLMClient]:
    reg = ToolRegistry()
    reg.register(EchoTool())
    fake = FakeLLMClient(responses)
    driver = LLMDriver(reg, client=fake, max_steps=3)
    return driver, fake


@pytest.mark.asyncio
async def test_driver_native_tool_call_parsed():
    """主路径：原生 tool_calls → AgentStep(is_final=False)。"""
    driver, _ = _build_driver([_tool_call_response("echo", {"text": "go"})])
    step = await driver.step([{"role": "user", "content": "q"}])
    assert step.is_final is False
    assert step.tool_call is not None
    assert step.tool_call.name == "echo"
    assert step.tool_call.arguments == {"text": "go"}
    assert step.tool_call.id == "call_test"  # 原生 id 透传


@pytest.mark.asyncio
async def test_driver_native_final_text_parsed():
    """主路径：无 tool_calls + 有 content → 最终文本。"""
    driver, _ = _build_driver([_final_response("只需要 summary 维度")])
    step = await driver.step([{"role": "user", "content": "q"}])
    assert step.is_final is True
    assert step.tool_call is None
    assert "summary 维度" in step.final_text


@pytest.mark.asyncio
async def test_driver_rejects_unregistered_native_tool():
    """原生返回未注册工具名 → 视为最终结果，保证 Loop 不发散。"""
    driver, _ = _build_driver([_tool_call_response("nonexistent", {})])
    step = await driver.step([{"role": "user", "content": "q"}])
    assert step.is_final is True


@pytest.mark.asyncio
async def test_driver_empty_response_becomes_final():
    """content 为空且无 tool_calls → 视为最终结果。"""
    driver, _ = _build_driver([_final_response("")])
    step = await driver.step([{"role": "user", "content": "q"}])
    assert step.is_final is True
    assert step.final_text == ""


@pytest.mark.asyncio
async def test_driver_llm_failure_propagates():
    """LLM 客户端抛 LLMClientError 时应向上抛，交由 Loop 降级。"""
    from app.core.llm import LLMClientError

    class FailClient:
        async def chat_with_tools(self, *a, **k):  # noqa: ARG002
            raise LLMClientError("down")

    reg = ToolRegistry()
    reg.register(EchoTool())
    driver = LLMDriver(reg, client=FailClient(), max_steps=3)
    with pytest.raises(LLMClientError):
        await driver.step([{"role": "user", "content": "q"}])
