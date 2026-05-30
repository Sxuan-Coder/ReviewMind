"""Security Agent：扫描 PR diff 中的安全问题，优先使用 LLM，降级为规则。"""

from __future__ import annotations

import logging
from uuid import uuid4

from app.agents.json_utils import try_parse_json
from app.agents.prompts import SECURITY_SYSTEM, build_user_prompt
from app.core.llm import LLMClientError, llm_client
from app.schemas.agents import AgentContext, AgentFindingsResult
from app.schemas.review import ReviewFinding

logger = logging.getLogger(__name__)


async def run_async(context: AgentContext) -> AgentFindingsResult:
    """异步版本，支持真实 LLM 调用。"""
    if llm_client.is_configured and not llm_client._mock_mode:
        try:
            messages = [
                {"role": "system", "content": SECURITY_SYSTEM},
                {"role": "user", "content": build_user_prompt(context)},
            ]
            logger.info("[SECURITY_AGENT] Calling LLM... files=%d", len(context.parsed_diff))
            raw = await llm_client.chat(messages, model=None, temperature=0.1)
            parsed = try_parse_json(raw)
            findings = [
                ReviewFinding(
                    id=str(f.get("id") or f"sec_{uuid4().hex[:8]}"),
                    agent="security_agent",
                    file=f.get("file") or "unknown",
                    line=int(f.get("line") or 0),
                    level=f.get("level", "INFO"),
                    type=f.get("type", "security_check"),
                    confidence=float(f.get("confidence", 0.5)),
                    description=f.get("description", ""),
                    suggestion=f.get("suggestion", ""),
                )
                for f in parsed.get("findings", [])
                if isinstance(f, dict)
            ]
            logger.info("[SECURITY_AGENT] LLM OK | findings=%d", len(findings))
            return AgentFindingsResult(
                agent="security_agent",
                findings=findings,
                summary=f"Security agent found {len(findings)} issues.",
            )
        except (LLMClientError, Exception) as exc:
            logger.warning("[SECURITY_AGENT] LLM failed, fallback to rules | %s: %s", type(exc).__name__, exc)

    logger.info("[SECURITY_AGENT] Using sync fallback (rules)")
    return run(context)


def run(context: AgentContext) -> AgentFindingsResult:
    """同步版本（mock / 降级路径）。"""
    findings = []
    for diff in context.parsed_diff:
        file = diff.get("file", "unknown")
        changed_lines = diff.get("changed_lines", [])
        if changed_lines:
            findings.append(
                ReviewFinding(
                    id=f"sec_{uuid4().hex[:8]}",
                    agent="security_agent",
                    file=file,
                    line=changed_lines[0],
                    level="INFO",
                    type="security_check",
                    confidence=0.8,
                    description=f"Security scan placeholder for {file}",
                    suggestion="Real security rules will be implemented in later PRs.",
                )
            )
    logger.info("[SECURITY_AGENT] Fallback findings=%d", len(findings))
    return AgentFindingsResult(
        agent="security_agent",
        findings=findings,
        summary="Mock security agent completed.",
    )
