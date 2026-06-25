"""PlannerAgent：基于 ReAct 循环产出审查计划。

这是 Agent Loop 的「决策层」。它通过一个 LLM + Tools 的循环：
1. 让 LLM 先调用只读探查工具（get_pr_overview / list_changed_files / ...）
   「看清」当前 PR 的特征；
2. 当 LLM 认为信息足够时，输出 ``FINAL_ANSWER`` 终止循环；
3. 从最终答案中解析出结构化的 ``ReviewPlan``（审查哪些维度、要不要 RAG）。

与现状（硬编码 ``_AGENT_NODES`` 列表）的根本区别：
- 现状：无脑跑全部 4 个 Agent，无论 PR 大小。
- Planner：根据 PR 特征动态裁剪——小 PR 可能只跑 summary，省 3 次 LLM 调用。

降级策略（保证鲁棒）：
- LLM 不可用 / 超过 max_steps / 解析失败 → ``fallback_plan``（退化为现状的
  全维度），确保系统不因 Planner 故障而不可用。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.agent_loop.agent_tools import build_planner_registry
from app.agent_loop.llm_driver import AgentStep, LLMDriver
from app.agent_loop.schemas import ContextSnapshot, DimensionTask, ReviewDimension, ReviewPlan
from app.core.llm import LLMClientError, llm_client

logger = logging.getLogger(__name__)


# Planner 的 System Prompt：教 LLM 用原生工具调用 + 产出最终计划
PLANNER_SYSTEM = """你是 ReviewMind 的审查计划制定者（Planner）。

你的任务：分析一个 GitHub PR，决定本次需要执行哪些审查维度。

## 审查维度
你可以在最终计划中选择以下维度的子集：
- summary: 变更摘要（任何 PR 都应包含）
- security: 安全审查（涉及认证/密码/SQL/输入时需要）
- performance: 性能审查（涉及查询/循环/IO 时需要）
- test: 测试质量审查（涉及测试文件或核心逻辑时需要）

## 决策原则
1. 小改动（如只改 README、文档）→ 只需 summary 维度
2. 涉及 auth/payment/config 等敏感路径 → 必须包含 security
3. 涉及数据库查询/循环/IO → 包含 performance
4. 涉及 .py/.ts 核心逻辑 → 考虑 test
5. 信息不够时，可以调用工具了解 PR；信息够了就尽快给出最终计划

## 输出要求
当你决定好审查计划后，直接用如下 JSON 结构回答（不要包裹在 markdown 代码块里）：
{"dimensions": [{"dimension": "summary", "use_rag": false, "rationale": "..."}, ...], "overall_risk_hint": "LOW/MEDIUM/HIGH", "reasoning": "一句话说明你的决策依据"}

注意：dimensions 列表至少包含 summary 维度。"""


class PlannerAgent:
    """ReAct 式 Planner：LLM + 探查工具 + 循环 → 审查计划。"""

    def __init__(
        self,
        snapshot: ContextSnapshot,
        *,
        client: Any | None = None,
        model: str | None = None,
        max_steps: int = 4,
        on_step: Any | None = None,
    ) -> None:
        self._snapshot = snapshot
        registry = build_planner_registry(snapshot)
        self._driver = LLMDriver(
            registry,
            client=client or llm_client,
            model=model,
            temperature=0.1,
            max_steps=max_steps,
        )
        self._max_steps = max_steps
        # 可观测回调：每步决策时调用 on_step(step_no, step, tool_result)
        # 供冒烟脚本/调试使用，不影响主流程。
        self._on_step = on_step

    async def plan(self) -> ReviewPlan:
        """运行 ReAct 循环，产出审查计划。

        任何异常（LLM 不可用、超步数、解析失败）都会降级到 fallback_plan，
        保证 ReviewOrchestrator 永远能拿到一个可用计划。
        """
        try:
            return await self._run_loop()
        except LLMClientError as exc:
            logger.warning("[PLANNER] LLM unavailable, using fallback plan: %s", exc)
            return self.fallback_plan(reason=f"llm_unavailable: {exc}")
        except Exception as exc:  # noqa: BLE001 — Planner 故障必须降级，不可中断主流程
            logger.exception("[PLANNER] unexpected error, using fallback plan")
            return self.fallback_plan(reason=f"planner_error: {exc}")

    async def _run_loop(self) -> ReviewPlan:
        """主 ReAct 循环（OpenAI 原生 Function Calling 多轮协议）。"""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": self._build_initial_user_msg()},
        ]

        for step_no in range(self._max_steps):
            step = await self._driver.step(messages)

            if step.is_final:
                # 模型给出最终文本 → 记录 assistant 消息并尝试解析计划
                messages.append({"role": "assistant", "content": step.final_text})
                plan = self._parse_plan(step.final_text)
                if plan is not None:
                    logger.info("[PLANNER] plan produced at step %d: %s", step_no, plan.dimension_names())
                    return plan
                # 解析失败 → 提示模型重新按格式输出
                logger.warning("[PLANNER] parse failed at step %d, final_text=%.200s", step_no, step.final_text)
                messages.append({
                    "role": "user",
                    "content": "上一次输出无法解析为有效的计划 JSON，请直接输出 JSON 计划（不要包裹代码块）。",
                })
                continue

            # 非终止：模型要求调用工具。按 OpenAI 多轮协议回灌：
            # 1) assistant 消息（带原始 tool_calls 结构）
            # 2) tool 消息（带 tool_call_id + 工具结果）
            assert step.tool_call is not None
            messages.append(self._build_assistant_tool_message(step))
            tool_result = await self._execute_tool(step.tool_call.name, step.tool_call.arguments)
            messages.append({
                "role": "tool",
                "tool_call_id": step.tool_call.id,
                "content": tool_result,
            })
            if self._on_step is not None:
                await self._on_step(step_no, step, tool_result)

        logger.warning("[PLANNER] exceeded max_steps=%d, using fallback plan", self._max_steps)
        return self.fallback_plan(reason="max_steps_exceeded")

    @staticmethod
    def _build_assistant_tool_message(step: AgentStep) -> dict[str, Any]:
        """构造 OpenAI 标准的 assistant 消息（含 tool_calls 结构）。

        多轮工具调用协议要求：回灌 tool 结果前，必须有一条带原始 tool_calls 的
        assistant 消息，且 tool 消息的 tool_call_id 与之对应。

        对于推理模型（如 deepseek-v4-flash），其 thinking mode 要求把上一步的
        ``reasoning_content`` 一并带回，否则 API 报 400。
        """
        msg: dict[str, Any] = {
            "role": "assistant",
            "content": step.reasoning or None,
            "tool_calls": [
                {
                    "id": step.tool_call.id if step.tool_call else "",
                    "type": "function",
                    "function": {
                        "name": step.tool_call.name if step.tool_call else "",
                        "arguments": json.dumps(step.tool_call.arguments, ensure_ascii=False) if step.tool_call else "{}",
                    },
                }
            ],
        }
        # 推理模型要求回灌 reasoning_content（仅当存在时携带，避免污染非推理模型）
        if step.reasoning_content:
            msg["reasoning_content"] = step.reasoning_content
        return msg

    async def _execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """执行一次工具调用并返回给 LLM 的观察文本。"""
        registry = self._driver._registry  # noqa: SLF001 — driver 内部注册表即本 Planner 构造的
        tool = registry.get(name)
        if tool is None:
            return f"[tool:{name}] ERROR: unknown tool"
        result = await tool.invoke(arguments)
        return result.to_llm_friendly()

    # ------------------------------------------------------------------
    # 计划解析
    # ------------------------------------------------------------------

    def _parse_plan(self, text: str) -> ReviewPlan | None:
        """从 LLM 最终答案文本中解析出 ReviewPlan。"""
        if not text:
            return None
        raw_json = self._extract_json(text)
        if raw_json is None:
            return None
        try:
            data = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(data, dict):
            return None

        dims_raw = data.get("dimensions", [])
        if not isinstance(dims_raw, list) or not dims_raw:
            return None

        dimensions: list[DimensionTask] = []
        for item in dims_raw:
            if not isinstance(item, dict):
                continue
            dim = self._coerce_dimension(item.get("dimension"))
            if dim is None:
                continue
            dimensions.append(
                DimensionTask(
                    dimension=dim,
                    use_rag=bool(item.get("use_rag", False)),
                    allow_fetch_full_file=bool(item.get("allow_fetch_full_file", False)),
                    rationale=str(item.get("rationale", "")),
                )
            )

        # 兜底：至少保证有 summary
        if not dimensions:
            dimensions.append(DimensionTask(dimension=ReviewDimension.SUMMARY, rationale="default"))

        return ReviewPlan(
            dimensions=dimensions,
            overall_risk_hint=str(data.get("overall_risk_hint", "")),
            reasoning=str(data.get("reasoning", "")),
        )

    @staticmethod
    def _coerce_dimension(value: Any) -> ReviewDimension | None:
        """把 LLM 输出的维度名容错转为枚举。"""
        if isinstance(value, ReviewDimension):
            return value
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        for d in ReviewDimension:
            if d.value == normalized:
                return d
        return None

    @staticmethod
    def _extract_json(text: str) -> str | None:
        """从文本中提取 JSON 对象（容错：代码块 / 裸 JSON）。"""
        # 1. 优先匹配 ```json ... ``` 代码块
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            return m.group(1)
        # 2. 匹配首个 { 到最后一个 } 之间的内容
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return m.group(0)
        return None

    # ------------------------------------------------------------------
    # 降级计划
    # ------------------------------------------------------------------

    def fallback_plan(self, *, reason: str = "") -> ReviewPlan:
        """降级计划：等同于现状的「全维度审查」。

        当 Planner 无法工作时，退化为跑全部 4 个 Agent，确保不丢审查能力。
        """
        logger.info("[PLANNER] using fallback plan (full dimensions): %s", reason)
        return ReviewPlan(
            dimensions=[
                DimensionTask(dimension=ReviewDimension.SUMMARY, rationale="fallback"),
                DimensionTask(dimension=ReviewDimension.SECURITY, rationale="fallback"),
                DimensionTask(dimension=ReviewDimension.PERFORMANCE, rationale="fallback"),
                DimensionTask(dimension=ReviewDimension.TEST, rationale="fallback"),
            ],
            overall_risk_hint="UNKNOWN",
            reasoning=f"fallback plan: {reason}",
        )

    # ------------------------------------------------------------------
    # 初始用户消息
    # ------------------------------------------------------------------

    def _build_initial_user_msg(self) -> str:
        """构建首轮用户提示：告诉 LLM 当前要分析的 PR。"""
        included = self._snapshot.filtered_files.get("included_files", [])
        file_names = [f.get("filename", "") for f in included if isinstance(f, dict)]
        return (
            f"请为以下 PR 制定审查计划。\n"
            f"PR 标题: {self._snapshot.pr_info.get('title', 'N/A')}\n"
            f"作者: {self._snapshot.pr_info.get('author', 'N/A')}\n"
            f"变更文件数: {len(included)}\n"
            f"文件清单: {', '.join(file_names[:20])}\n\n"
            f"你可以调用工具获取更多信息，或直接给出最终计划。"
        )
