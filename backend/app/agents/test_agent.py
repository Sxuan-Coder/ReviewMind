"""Test Agent：检测 PR diff 中的测试覆盖问题，优先使用 LLM，降级为规则。"""

from __future__ import annotations

import json
import logging
from uuid import uuid4

from app.agents.prompts import TEST_SYSTEM, build_user_prompt
from app.core.llm import LLMClientError, llm_client
from app.schemas.agents import AgentContext, AgentFindingsResult
from app.schemas.review import ReviewFinding

logger = logging.getLogger(__name__)


async def run_async(context: AgentContext) -> AgentFindingsResult:
    """异步版本，支持真实 LLM 调用。"""
    if llm_client.is_configured and not llm_client._mock_mode:
        try:
            messages = [
                {"role": "system", "content": TEST_SYSTEM},
                {"role": "user", "content": build_user_prompt(context)},
            ]
            logger.info("[TEST_AGENT] Calling LLM... files=%d", len(context.parsed_diff))
            raw = await llm_client.chat(messages, model=None, temperature=0.1)
            parsed = _try_parse_json(raw)
            findings = [
                ReviewFinding(
                    id=f.get("id", f"test_{uuid4().hex[:8]}"),
                    agent="test_agent",
                    file=f.get("file", "unknown"),
                    line=f.get("line", 0),
                    level=f.get("level", "INFO"),
                    type=f.get("type", "test_check"),
                    confidence=float(f.get("confidence", 0.5)),
                    description=f.get("description", ""),
                    suggestion=f.get("suggestion", ""),
                )
                for f in parsed.get("findings", [])
                if isinstance(f, dict)
            ]
            logger.info("[TEST_AGENT] LLM OK | findings=%d", len(findings))
            return AgentFindingsResult(
                agent="test_agent",
                findings=findings,
                summary=f"Test agent found {len(findings)} issues.",
            )
        except (LLMClientError, Exception) as exc:
            logger.warning("[TEST_AGENT] LLM failed, fallback to rules | %s: %s", type(exc).__name__, exc)

    logger.info("[TEST_AGENT] Using sync fallback (rules)")
    return run(context)


def run(context: AgentContext) -> AgentFindingsResult:
    """同步版本（mock / 降级路径）。"""
    findings = []
    for diff in context.parsed_diff:
        file = diff.get("file", "unknown")
        if file.startswith("test") or "test" in file.lower():
            findings.append(
                ReviewFinding(
                    id=f"test_{uuid4().hex[:8]}",
                    agent="test_agent",
                    file=file,
                    line=1,
                    level="INFO",
                    type="test_file_changed",
                    confidence=0.9,
                    description=f"Test file modified: {file}",
                    suggestion="Ensure test coverage is maintained.",
                )
            )
    logger.info("[TEST_AGENT] Fallback findings=%d", len(findings))
    return AgentFindingsResult(
        agent="test_agent",
        findings=findings,
        summary="Mock test agent completed.",
    )


def _try_parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        if "```json" in raw:
            try:
                start = raw.index("```json") + 7
                end = raw.index("```", start)
                return json.loads(raw[start:end].strip())
            except (ValueError, json.JSONDecodeError):
                pass
        if "```" in raw:
            try:
                start = raw.index("```") + 3
                end = raw.index("```", start)
                return json.loads(raw[start:end].strip())
            except (ValueError, json.JSONDecodeError):
                pass
        return {"findings": []}
