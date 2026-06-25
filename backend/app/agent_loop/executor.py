"""Executor：按 Planner 产出的审查计划并行执行各维度。

职责：
- 接收 ReviewPlan，对其中每个 DimensionTask 调用 analyze_dimension 工具；
- 无数据依赖的维度并行执行（保留现状 asyncio.gather 的并行优势）；
- 把每个工具调用的原始 result（AgentFindingsResult）还原出来，交给 Finalizer。

设计要点：
- Executor 本身不调 LLM、不做决策——它只「忠实执行计划」。决策权在 Planner，
  聚合权在 Finalizer。这种职责分离让每一层都可独立测试与替换。
- 单个维度失败不影响其他维度：失败的维度记为 success=False，其他继续。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import BaseModel

from app.agent_loop.agent_tools import AnalyzeDimensionTool
from app.agent_loop.schemas import (
    ContextSnapshot,
    DimensionResult,
    DimensionTask,
    ReviewDimension,
    ReviewPlan,
)
from app.schemas.agents import AgentFindingsResult

logger = logging.getLogger(__name__)


class Executor:
    """按计划并行执行各审查维度。"""

    def __init__(self, snapshot: ContextSnapshot) -> None:
        self._snapshot = snapshot
        self._analyze_tool = AnalyzeDimensionTool(snapshot)

    async def execute(self, plan: ReviewPlan) -> list[DimensionResult]:
        """并行执行计划中的所有维度任务，返回每个维度的结果。"""
        if not plan.dimensions:
            logger.warning("[EXECUTOR] empty plan, nothing to execute")
            return []

        tasks = [self._execute_one(task) for task in plan.dimensions]
        # return_exceptions 已由 Tool.invoke 内部捕获，这里 gather 不需再捕获；
        # 但保留 return_exceptions=True 作为第二道防线。
        results = await asyncio.gather(*tasks, return_exceptions=True)

        dimension_results: list[DimensionResult] = []
        for task, res in zip(plan.dimensions, results):
            if isinstance(res, Exception):
                logger.error("[EXECUTOR] dimension %s raised: %s", task.dimension, res)
                dimension_results.append(
                    DimensionResult(
                        dimension=task.dimension,
                        success=False,
                        error=f"{type(res).__name__}: {res}",
                    )
                )
            else:
                dimension_results.append(res)
        return dimension_results

    async def _execute_one(self, task: DimensionTask) -> DimensionResult:
        """执行单个维度任务。"""
        tool_result = await self._analyze_tool.invoke(
            {
                "dimension": task.dimension.value,
                "use_rag": task.use_rag,
            }
        )
        if not tool_result.success:
            return DimensionResult(
                dimension=task.dimension,
                success=False,
                error=tool_result.error,
            )

        # 从工具输出中还原 AgentFindingsResult，供 Finalizer 聚合
        output = tool_result.output or {}
        raw_result = output.get("_result")
        agent_result: AgentFindingsResult | None = None
        if isinstance(raw_result, dict):
            try:
                agent_result = AgentFindingsResult.model_validate(raw_result)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[EXECUTOR] failed to restore AgentFindingsResult: %s", exc)

        return DimensionResult(
            dimension=task.dimension,
            success=bool(output.get("ok", True)),
            result=agent_result,
            error="" if output.get("ok") else str(output.get("error", "")),
        )
