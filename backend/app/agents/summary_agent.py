"""Summary Agent：生成 PR 总体摘要，优先使用 LLM，降级为规则。"""

from __future__ import annotations

import logging

from app.agents.json_utils import try_parse_json
from app.agents.prompts import SUMMARY_SYSTEM, build_user_prompt
from app.core.llm import LLMClientError, llm_client
from app.schemas.agents import AgentContext, AgentFindingsResult

logger = logging.getLogger(__name__)


async def run_async(context: AgentContext) -> AgentFindingsResult:
    """异步版本，支持真实 LLM 调用。"""
    if llm_client.is_configured and not llm_client._mock_mode:
        try:
            messages = [
                {"role": "system", "content": SUMMARY_SYSTEM},
                {"role": "user", "content": build_user_prompt(context)},
            ]
            logger.info("[SUMMARY_AGENT] Calling LLM... files=%d", len(context.parsed_diff))
            raw = await llm_client.chat(messages, model=None, temperature=0.2)
            parsed = try_parse_json(raw, fallback_key="summary")
            logger.info("[SUMMARY_AGENT] LLM OK | summary_len=%d findings=%d",
                        len(parsed.get("summary", "")), len(parsed.get("findings", [])))
            return AgentFindingsResult(
                agent="summary_agent",
                summary=parsed.get("summary", _fallback_summary(context)),
                findings=[],
            )
        except (LLMClientError, Exception) as exc:
            logger.warning("[SUMMARY_AGENT] LLM failed, fallback to rules | %s: %s", type(exc).__name__, exc)

    logger.info("[SUMMARY_AGENT] Using sync fallback (rules)")
    return run(context)


def run(context: AgentContext) -> AgentFindingsResult:
    """同步版本（mock / 降级路径）。"""
    summary = _fallback_summary(context)
    logger.info("[SUMMARY_AGENT] Fallback summary: %s", summary)
    return AgentFindingsResult(
        agent="summary_agent",
        summary=summary,
        findings=[],
    )


def _fallback_summary(context: AgentContext) -> str:
    files = [diff.get("file", "unknown") for diff in context.parsed_diff]
    return f"PR 涉及 {len(files)} 个文件变更，正在进行基础 Diff 分析。"