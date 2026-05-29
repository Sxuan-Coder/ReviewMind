"""Tests for real agent prompt integration — mock mode and LLM error fallback."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.agents import security_agent, summary_agent, performance_agent, test_agent
from app.schemas.agents import AgentContext


SAMPLE_DIFF = [
    {
        "file": "src/services/auth_service.py",
        "status": "modified",
        "additions": 15,
        "deletions": 3,
        "changed_lines": [10, 11, 12, 30],
        "patch": "@@ -8,6 +8,18 @@\n def login(username, password):\n-    user = db.query(f\"SELECT * FROM users WHERE name='{username}'\")\n+    user = db.query(\"SELECT * FROM users WHERE name=%s\", (username,))\n+    return user\n",
    },
    {
        "file": "tests/test_auth_service.py",
        "status": "modified",
        "additions": 8,
        "deletions": 1,
        "changed_lines": [5, 6, 7],
        "patch": "@@ -3,4 +3,11 @@\n import pytest\n+from app.services.auth_service import login\n+\n+def test_login_valid_user():\n+    assert login(\"admin\", \"pass\") is not None\n",
    },
]


def make_context(parsed_diff=None):
    return AgentContext(
        pr_info={"title": "Fix SQL injection in login", "author": "alice"},
        parsed_diff=parsed_diff or SAMPLE_DIFF,
    )


def test_summary_agent_mock_mode():
    """mock 模式下 summary_agent 使用降级逻辑。"""
    result = summary_agent.run(make_context())
    assert result.agent == "summary_agent"
    assert "2" in result.summary or "文件" in result.summary
    assert result.findings == []


def test_security_agent_mock_mode():
    """mock 模式下 security_agent 使用规则逻辑。"""
    result = security_agent.run(make_context())
    assert result.agent == "security_agent"
    assert len(result.findings) == 2
    assert result.findings[0].agent == "security_agent"


def test_performance_agent_mock_mode():
    """mock 模式下 performance_agent 使用规则逻辑。"""
    result = performance_agent.run(make_context())
    assert result.agent == "performance_agent"
    # additions=15 < 50, no findings
    assert len(result.findings) == 0


def test_performance_agent_flags_large_change():
    large_diff = [{"file": "big.py", "status": "modified", "additions": 100, "deletions": 5, "changed_lines": [1]}]
    result = performance_agent.run(make_context(large_diff))
    assert len(result.findings) == 1
    assert result.findings[0].level == "WARNING"


def test_test_agent_mock_mode():
    """mock 模式下 test_agent 使用规则逻辑。"""
    result = test_agent.run(make_context())
    assert result.agent == "test_agent"
    assert len(result.findings) == 1
    assert "test" in result.findings[0].file.lower()


@pytest.mark.anyio
async def test_summary_agent_run_async_mock_mode():
    """run_async 在 mock 模式下走降级路径。"""
    result = await summary_agent.run_async(make_context())
    assert result.agent == "summary_agent"
    assert result.summary


@pytest.mark.anyio
async def test_security_agent_run_async_mock_mode():
    """run_async 在 mock 模式下走降级路径。"""
    result = await security_agent.run_async(make_context())
    assert result.agent == "security_agent"
    assert len(result.findings) == 2


@pytest.mark.anyio
async def test_agents_handle_empty_diff():
    """空 diff 不应产生 findings。"""
    ctx = AgentContext(pr_info={}, parsed_diff=[], ast_contexts=[])
    assert summary_agent.run(ctx).agent == "summary_agent"
    assert len(security_agent.run(ctx).findings) == 0
    assert len(performance_agent.run(ctx).findings) == 0
    assert len(test_agent.run(ctx).findings) == 0


@pytest.mark.anyio
async def test_summary_agent_run_async_uses_llm_when_configured():
    """当 LLM 已配置且非 mock 模式时，run_async 应调用 LLM。"""
    mock_llm_response = json.dumps({
        "summary": "This PR fixes SQL injection in the login function.",
        "findings": [],
        "risk_level": "LOW",
    })

    with patch.object(summary_agent, "llm_client") as mock_client:
        mock_client.is_configured = True
        mock_client._mock_mode = False
        mock_client.chat = AsyncMock(return_value=mock_llm_response)

        result = await summary_agent.run_async(make_context())

        assert result.agent == "summary_agent"
        assert "SQL injection" in result.summary
        mock_client.chat.assert_called_once()


@pytest.mark.anyio
async def test_security_agent_run_async_uses_llm_when_configured():
    """当 LLM 已配置且非 mock 模式时，security_agent run_async 应调用 LLM。"""
    mock_llm_response = json.dumps({
        "findings": [
            {
                "id": "sec_001",
                "file": "src/services/auth_service.py",
                "line": 10,
                "level": "CRITICAL",
                "type": "sql_injection",
                "confidence": 0.95,
                "description": "SQL injection via string formatting",
                "suggestion": "Use parameterized queries",
            }
        ]
    })

    with patch.object(security_agent, "llm_client") as mock_client:
        mock_client.is_configured = True
        mock_client._mock_mode = False
        mock_client.chat = AsyncMock(return_value=mock_llm_response)

        result = await security_agent.run_async(make_context())

        assert result.agent == "security_agent"
        assert len(result.findings) == 1
        assert result.findings[0].level == "CRITICAL"
        assert result.findings[0].type == "sql_injection"


@pytest.mark.anyio
async def test_agent_falls_back_on_llm_error():
    """LLM 调用失败时应降级为 mock 逻辑。"""
    with patch.object(summary_agent, "llm_client") as mock_client:
        mock_client.is_configured = True
        mock_client._mock_mode = False
        mock_client.chat = AsyncMock(side_effect=summary_agent.LLMClientError("timeout"))

        result = await summary_agent.run_async(make_context())

        assert result.agent == "summary_agent"
        assert result.summary  # fallback produced something


@pytest.mark.anyio
async def test_agent_falls_back_on_invalid_llm_json():
    """LLM 返回无效 JSON 时应降级为 mock 逻辑。"""
    with patch.object(summary_agent, "llm_client") as mock_client:
        mock_client.is_configured = True
        mock_client._mock_mode = False
        mock_client.chat = AsyncMock(return_value="This is not JSON at all")

        result = await summary_agent.run_async(make_context())

        assert result.agent == "summary_agent"
        assert result.summary  # fallback or raw text truncated