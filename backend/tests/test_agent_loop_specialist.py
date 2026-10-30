"""Tests for SpecialistAgent 与 agentic security worker 接入。"""

from __future__ import annotations

import base64

import httpx
import pytest

from app.agent_loop.agent_tools import (
    AnalyzeDimensionTool,
    FetchFileContentTool,
    GetAstContextTool,
    GetFileDiffTool,
    SearchSimilarCodeTool,
    build_security_worker_registry,
)
from app.agent_loop.schemas import ContextSnapshot, ReviewDimension
from app.agent_loop.specialist import SpecialistAgent, SpecialistError
from app.core.llm import ToolCallItem, ToolCallResponse
from app.services.github_client import GitHubClient, GitHubClientError


def _make_snapshot() -> ContextSnapshot:
    return ContextSnapshot(
        job_id="job-1",
        pr_url="https://github.com/o/r/pull/1",
        pr_info={
            "title": "Add login",
            "author": "bob",
            "owner": "o",
            "repo": "r",
            "head": {"ref": "feature", "sha": "abc123"},
        },
        filtered_files={
            "included_files": [
                {"filename": "app/auth.py", "status": "modified", "additions": 10, "deletions": 2},
            ]
        },
        parsed_diff=[
            {
                "file": "app/auth.py",
                "additions": 10,
                "deletions": 2,
                "changed_lines": [12, 13, 14],
                "patch": "+password = request.args['pw']",
            }
        ],
        ast_contexts=[
            {"file": "app/auth.py", "symbol": "login", "start_line": 10, "end_line": 20, "code": "def login(): ..."}
        ],
        rag_contexts=[],
        tech_stack_prompt="Tech stack: FastAPI",
    )


class FakeLLMClient:
    """伪 LLM：按队列返回原生 ToolCallResponse。"""

    def __init__(self, responses: list[ToolCallResponse]) -> None:
        self._responses = list(responses)

    async def chat_with_tools(self, messages, *, tools, model=None, temperature=0.0, tool_choice="auto"):  # noqa: ARG002
        if not self._responses:
            return ToolCallResponse(content="{}", tool_calls=[], finish_reason="stop")
        return self._responses.pop(0)


class FailLLMClient:
    """伪 LLM：始终抛 LLMClientError。"""

    async def chat_with_tools(self, messages, *, tools, model=None, temperature=0.0, tool_choice="auto"):  # noqa: ARG002
        from app.core.llm import LLMClientError

        raise LLMClientError("llm down")


def _tool_call_resp(name, arguments=None, call_id="call_1") -> ToolCallResponse:
    return ToolCallResponse(
        content=None,
        tool_calls=[ToolCallItem(id=call_id, name=name, arguments=arguments or {})],
        finish_reason="tool_calls",
    )


def _final_resp(text: str) -> ToolCallResponse:
    return ToolCallResponse(content=text, tool_calls=[], finish_reason="stop")


# ---------------------------------------------------------------------------
# SpecialistAgent ReAct 循环
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_specialist_tool_loop_then_final():
    """LLM 先调工具（get_file_diff）再给最终 findings → 循环正常运转。"""
    snap = _make_snapshot()
    registry = build_security_worker_registry(snap)
    fake = FakeLLMClient([
        _tool_call_resp("get_file_diff", {"filename": "app/auth.py"}),
        _final_resp(
            '{"findings": [{"id": "sec_1", "agent": "security_agent", "file": "app/auth.py", '
            '"line": 12, "level": "HIGH", "type": "hardcoded_secret", "confidence": 0.9, '
            '"description": "硬编码密码", "suggestion": "改用环境变量"}], "summary": "发现 1 个问题"}'
        ),
    ])
    agent = SpecialistAgent(
        system_prompt="test", registry=registry, snapshot=snap,
        agent_name="security", client=fake, max_steps=4,
    )
    result = await agent.analyze()
    assert result.agent == "security_agent"
    assert len(result.findings) == 1
    assert result.findings[0].level == "HIGH"
    assert result.findings[0].description == "硬编码密码"


@pytest.mark.asyncio
async def test_specialist_llm_failure_raises_specialist_error():
    """LLM 不可用 → 抛 SpecialistError（调用方据此降级）。"""
    snap = _make_snapshot()
    registry = build_security_worker_registry(snap)
    agent = SpecialistAgent(
        system_prompt="test", registry=registry, snapshot=snap,
        agent_name="security", client=FailLLMClient(), max_steps=3,
    )
    with pytest.raises(SpecialistError):
        await agent.analyze()


@pytest.mark.asyncio
async def test_specialist_json_retry_then_success():
    """首次最终答案非 JSON → 追加纠正消息后第二次成功。"""
    snap = _make_snapshot()
    registry = build_security_worker_registry(snap)
    fake = FakeLLMClient([
        _final_resp('{"summary": "忘了带 findings 键"}'),  # 缺 findings 键
        _final_resp('{"findings": [], "summary": "无问题"}'),
    ])
    agent = SpecialistAgent(
        system_prompt="test", registry=registry, snapshot=snap,
        agent_name="security", client=fake, max_steps=4,
    )
    result = await agent.analyze()
    assert result.findings == []
    assert result.summary == "无问题"


@pytest.mark.asyncio
async def test_specialist_max_steps_exceeded():
    """LLM 一直调工具不终止 → 超过 max_steps 抛 SpecialistError。"""
    snap = _make_snapshot()
    registry = build_security_worker_registry(snap)
    fake = FakeLLMClient([
        _tool_call_resp("get_file_diff", {"filename": "app/auth.py"}) for _ in range(5)
    ])
    agent = SpecialistAgent(
        system_prompt="test", registry=registry, snapshot=snap,
        agent_name="security", client=fake, max_steps=3,
    )
    with pytest.raises(SpecialistError, match="max_steps"):
        await agent.analyze()


# ---------------------------------------------------------------------------
# Worker 工具
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_file_diff_tool():
    tool = GetFileDiffTool(_make_snapshot())
    result = await tool.invoke({"filename": "app/auth.py"})
    assert result.success
    assert result.output["changed_lines"] == [12, 13, 14]


@pytest.mark.asyncio
async def test_get_file_diff_tool_missing_file():
    tool = GetFileDiffTool(_make_snapshot())
    result = await tool.invoke({"filename": "nope.py"})
    assert result.success
    assert "error" in result.output


@pytest.mark.asyncio
async def test_get_ast_context_tool():
    tool = GetAstContextTool(_make_snapshot())
    result = await tool.invoke({"filename": "app/auth.py"})
    assert result.success
    assert result.output["contexts"][0]["symbol"] == "login"


@pytest.mark.asyncio
async def test_fetch_file_content_tool_with_fake_client():
    class FakeGH:
        async def get_file_contents(self, owner, repo, path, ref=None):
            assert (owner, repo, path) == ("o", "r", "app/auth.py")
            assert ref == "abc123"  # 默认取 PR head sha
            return "def login(): pass"

    tool = FetchFileContentTool(_make_snapshot(), FakeGH())
    result = await tool.invoke({"path": "app/auth.py"})
    assert result.success
    assert result.output["content"] == "def login(): pass"


@pytest.mark.asyncio
async def test_search_similar_code_tool_rag_failure_degrades():
    """RAG 检索抛异常 → 返回 error 字段而非崩溃。"""

    class BrokenRetriever:
        async def aretrieve(self, query, *, top_k=None):
            raise RuntimeError("vector store down")

    tool = SearchSimilarCodeTool(_make_snapshot(), retriever=BrokenRetriever())
    result = await tool.invoke({"query": "app/auth.py"})
    assert result.success
    assert "error" in result.output


def test_security_registry_with_and_without_fetch():
    snap = _make_snapshot()
    reg = build_security_worker_registry(snap, github_client=object())
    assert "fetch_file_content" in reg.names()
    reg2 = build_security_worker_registry(snap, github_client=None)
    assert "fetch_file_content" not in reg2.names()


# ---------------------------------------------------------------------------
# AnalyzeDimensionTool agentic 接入与降级
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_security_agentic_path(monkeypatch):
    """开关开启时 security 维度走 SpecialistAgent（通过 monkeypatch 验证）。"""
    snap = _make_snapshot()
    from app.core.config import settings

    monkeypatch.setattr(settings, "review_agentic_workers", True)

    called = {}

    async def fake_analyze(self):
        called["yes"] = True
        from app.schemas.agents import AgentFindingsResult

        return AgentFindingsResult(agent="security_agent", findings=[], summary="agentic")

    monkeypatch.setattr(SpecialistAgent, "analyze", fake_analyze)

    tool = AnalyzeDimensionTool(snap)
    result = await tool.invoke({"dimension": "security"})
    assert result.success
    assert called.get("yes") is True
    assert result.output["_result"]["summary"] == "agentic"


@pytest.mark.asyncio
async def test_analyze_security_fallback_on_specialist_error(monkeypatch):
    """agentic 循环失败 → 自动降级回单次调用路径，结果仍有效。"""
    snap = _make_snapshot()
    from app.core.config import settings

    monkeypatch.setattr(settings, "review_agentic_workers", True)

    async def fake_analyze(self):
        raise SpecialistError("max_steps_exceeded")

    monkeypatch.setattr(SpecialistAgent, "analyze", fake_analyze)

    async def fake_run_async(ctx):
        from app.schemas.agents import AgentFindingsResult

        return AgentFindingsResult(agent="security_agent", findings=[], summary="one-shot fallback")

    monkeypatch.setattr("app.agents.security_agent.run_async", fake_run_async)

    tool = AnalyzeDimensionTool(snap)
    result = await tool.invoke({"dimension": "security"})
    assert result.success
    assert result.output["_result"]["summary"] == "one-shot fallback"


@pytest.mark.asyncio
async def test_analyze_security_agentic_disabled(monkeypatch):
    """开关关闭时 security 维度直接走单次调用路径。"""
    snap = _make_snapshot()
    from app.core.config import settings

    monkeypatch.setattr(settings, "review_agentic_workers", False)

    async def fail_analyze(self):
        raise AssertionError("should not run agentic path")

    monkeypatch.setattr(SpecialistAgent, "analyze", fail_analyze)

    async def fake_run_async(ctx):
        from app.schemas.agents import AgentFindingsResult

        return AgentFindingsResult(agent="security_agent", findings=[], summary="one-shot")

    monkeypatch.setattr("app.agents.security_agent.run_async", fake_run_async)

    tool = AnalyzeDimensionTool(snap)
    result = await tool.invoke({"dimension": "security"})
    assert result.success
    assert result.output["_result"]["summary"] == "one-shot"


# ---------------------------------------------------------------------------
# GitHubClient.get_file_contents
# ---------------------------------------------------------------------------


def _b64(content: str) -> str:
    return base64.b64encode(content.encode("utf-8")).decode("ascii")


def _gh_client_with(payload: dict, status: int = 200) -> GitHubClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload)

    http = httpx.AsyncClient(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    return GitHubClient(client=http)


@pytest.mark.asyncio
async def test_get_file_contents_success():
    gh = _gh_client_with({"encoding": "base64", "content": _b64("print('hi')")})
    content = await gh.get_file_contents("o", "r", "app/main.py", ref="abc")
    assert content == "print('hi')"


@pytest.mark.asyncio
async def test_get_file_contents_not_found():
    gh = _gh_client_with({"message": "Not Found"}, status=404)
    with pytest.raises(GitHubClientError):
        await gh.get_file_contents("o", "r", "missing.py")


@pytest.mark.asyncio
async def test_get_file_contents_non_text():
    gh = _gh_client_with({"encoding": "none", "content": None})
    with pytest.raises(GitHubClientError, match="not a text file"):
        await gh.get_file_contents("o", "r", "logo.png")
