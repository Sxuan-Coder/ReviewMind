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
from app.agent_loop.llm_driver import LLMDriver
from app.agent_loop.schemas import ContextSnapshot, DimensionTask, ReviewDimension, ReviewPlan
from app.core.llm import LLMClientError, llm_client

logger = logging.getLogger(__name__)


# Planner 的 System Prompt：教 LLM 如何用工具 + 如何产出最终计划
PLANNER_SYSTEM = """你是 ReviewMind 的审查计划制定者（Planner）。

你的任务：分析一个 GitHub PR，决定本次需要执行哪些审查维度。

## 可用工具
你可以调用以下只读工具来了解 PR：
- get_pr_overview: 获取 PR 标题、作者、变更规模
- list_changed_files: 列出变更文件
- detect_tech_stack: 检测项目技术栈

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
5. 避免无谓调用工具：信息够就尽快给出最终答案

## 输出格式
当你需要调用工具时，输出：
TOOL_CALL: {"name": "工具名", "arguments": {...}}

当你信息足够、准备给出最终计划时，输出：
FINAL_ANSWER: <一段 JSON>，JSON 必须是如下结构：
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
        """主 ReAct 循环。"""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": self._build_initial_user_msg()},
        ]

        for step_no in range(self._max_steps):
            step = await self._driver.step(messages)
            messages.append({"role": "assistant", "content": step.reasoning or step.final_text})

            if step.is_final:
                plan = self._parse_plan(step.final_text)
                if plan is not None:
                    logger.info("[PLANNER] plan produced at step %d: %s", step_no, plan.dimension_names())
                    return plan
                # 解析失败 → 继续循环让 LLM 再试，或最终降级
                logger.warning("[PLANNER] parse failed at step %d, final_text=%.200s", step_no, step.final_text)
                messages.append({
                    "role": "user",
                    "content": "上一次输出无法解析为有效的计划 JSON，请严格按格式重新输出 FINAL_ANSWER。",
                })
                continue

            # 非终止：执行工具，把观察回灌给 LLM
            assert step.tool_call is not None
            tool_result = await self._execute_tool(step.tool_call.name, step.tool_call.arguments)
            messages.append({"role": "user", "content": tool_result})

        logger.warning("[PLANNER] exceeded max_steps=%d, using fallback plan", self._max_steps)
        return self.fallback_plan(reason="max_steps_exceeded")

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
