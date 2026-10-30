"""SpecialistAgent：维度级 Agentic Worker（ReAct 循环）。

与 Planner（决策层）相对，SpecialistAgent 是「执行层」的 agentic 升级：
不再收到一份预拼好的 prompt 一次性输出结论，而是在 ReAct 循环中自主调用
只读上下文工具（get_file_diff / get_ast_context / search_similar_code /
fetch_file_content），直到它认为证据充分后再输出结构化 findings。

这是 Phase 1 试点（security 维度）的通用载体：后续 Phase 2 铺开其他维度时，
只需提供不同的 system prompt 与工具注册表，循环机制完全复用。

降级策略（与 PlannerAgent 一致的鲁棒性原则）：
- LLM 不可用 / 超过 max_steps / JSON 始终无法解析 → 抛出 SpecialistError，
  由调用方（AnalyzeDimensionTool）回退到现有单次调用路径，保证「永不比现状差」。
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from app.agent_loop.llm_driver import AgentStep, LLMDriver
from app.agent_loop.planner import PlannerAgent  # 复用 _build_assistant_tool_message
from app.agent_loop.schemas import ContextSnapshot
from app.agent_loop.tools import ToolRegistry
from app.agents.json_utils import try_parse_json
from app.core.llm import LLMClientError, llm_client
from app.schemas.agents import AgentFindingsResult
from app.schemas.review import ReviewFinding

logger = logging.getLogger(__name__)


class SpecialistError(RuntimeError):
    """Specialist ReAct 循环失败，调用方应降级到单次调用路径。"""


class SpecialistAgent:
    """通用维度 Worker：LLM + 只读工具 + ReAct 循环 → AgentFindingsResult。"""

    def __init__(
        self,
        *,
        system_prompt: str,
        registry: ToolRegistry,
        snapshot: ContextSnapshot,
        agent_name: str,
        client: Any | None = None,
        model: str | None = None,
        max_steps: int = 8,
        on_step: Any | None = None,
    ) -> None:
        self._snapshot = snapshot
        self._agent_name = agent_name
        self._system_prompt = system_prompt
        self._driver = LLMDriver(
            registry,
            client=client or llm_client,
            model=model,
            temperature=0.0,
            max_steps=max_steps,
        )
        self._max_steps = max_steps
        self._on_step = on_step

    async def analyze(self) -> AgentFindingsResult:
        """运行 ReAct 循环，产出该维度的 findings。

        Raises:
            SpecialistError: 循环无法产出可解析结果（调用方应降级到单次调用）。
        """
        try:
            return await self._run_loop()
        except LLMClientError as exc:
            raise SpecialistError(f"llm_unavailable: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 — 任何异常都转为可降级信号
            logger.exception("[SPECIALIST:%s] unexpected error", self._agent_name)
            raise SpecialistError(f"specialist_error: {exc}") from exc

    async def _run_loop(self) -> AgentFindingsResult:
        """主 ReAct 循环（复用 Planner 的 OpenAI 原生 Function Calling 多轮协议）。"""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": self._build_initial_user_msg()},
        ]

        for step_no in range(self._max_steps):
            step = await self._driver.step(messages)

            if step.is_final:
                messages.append({"role": "assistant", "content": step.final_text})
                findings = self._parse_findings(step.final_text)
                if findings is not None:
                    logger.info(
                        "[SPECIALIST:%s] result at step %d | findings=%d",
                        self._agent_name, step_no, len(findings.findings),
                    )
                    return findings
                logger.warning(
                    "[SPECIALIST:%s] parse failed at step %d", self._agent_name, step_no
                )
                messages.append({
                    "role": "user",
                    "content": "上一次输出无法解析为有效的 findings JSON，请直接输出 JSON（不要包裹代码块）。",
                })
                continue

            assert step.tool_call is not None
            messages.append(PlannerAgent._build_assistant_tool_message(step))
            tool_result = await self._execute_tool(step.tool_call.name, step.tool_call.arguments)
            messages.append({
                "role": "tool",
                "tool_call_id": step.tool_call.id,
                "content": tool_result,
            })
            if self._on_step is not None:
                await self._on_step(step_no, step, tool_result)

        raise SpecialistError("max_steps_exceeded")

    async def _execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """执行一次工具调用并返回给 LLM 的观察文本。"""
        registry = self._driver._registry  # noqa: SLF001 — registry 即构造时传入的注册表
        tool = registry.get(name)
        if tool is None:
            return f"[tool:{name}] ERROR: unknown tool"
        result = await tool.invoke(arguments)
        return result.to_llm_friendly()

    # ------------------------------------------------------------------
    # 结果解析
    # ------------------------------------------------------------------

    def _parse_findings(self, text: str) -> AgentFindingsResult | None:
        """从 LLM 最终答案中解析 findings（容错解析，失败返回 None）。"""
        if not text:
            return None
        parsed = try_parse_json(text)
        if not isinstance(parsed, dict) or "findings" not in parsed:
            return None
        findings: list[ReviewFinding] = []
        for f in parsed.get("findings", []):
            if not isinstance(f, dict):
                continue
            try:
                findings.append(
                    ReviewFinding(
                        id=str(f.get("id") or f"{self._agent_name}_{uuid4().hex[:8]}"),
                        agent=str(f.get("agent") or f"{self._agent_name}_agent"),
                        file=f.get("file") or "unknown",
                        line=int(f.get("line") or 0),
                        level=str(f.get("level", "INFO")),
                        type=str(f.get("type", "agentic_check")),
                        confidence=float(f.get("confidence", 0.5)),
                        description=f.get("description", ""),
                        suggestion=f.get("suggestion", ""),
                    )
                )
            except (TypeError, ValueError):
                logger.warning("[SPECIALIST:%s] skip malformed finding: %r", self._agent_name, f)
        summary = str(parsed.get("summary") or f"{self._agent_name} agent completed (agentic).")
        return AgentFindingsResult(agent=f"{self._agent_name}_agent", findings=findings, summary=summary)

    # ------------------------------------------------------------------
    # 初始用户消息
    # ------------------------------------------------------------------

    def _build_initial_user_msg(self) -> str:
        """构建首轮用户提示：PR 概览 + 变更文件清单 + 工具指引。"""
        included = self._snapshot.filtered_files.get("included_files", [])
        file_names = [f.get("filename", "") for f in included if isinstance(f, dict)]
        tech = self._snapshot.tech_stack_prompt or "未检测"
        return (
            f"请审查以下 PR。\n"
            f"PR 标题: {self._snapshot.pr_info.get('title', 'N/A')}\n"
            f"作者: {self._snapshot.pr_info.get('author', 'N/A')}\n"
            f"技术栈: {tech[:200]}\n"
            f"变更文件数: {len(included)}\n"
            f"文件清单: {', '.join(file_names[:30])}\n\n"
            f"建议先用 get_file_diff 逐个查看变更文件；diff 不足以判断时再拉取完整文件或 AST 上下文。"
            f"分析完成后直接输出最终 JSON。"
        )
