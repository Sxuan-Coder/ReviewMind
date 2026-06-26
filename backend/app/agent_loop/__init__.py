"""Agent Loop 模块：基于 ReAct / Plan-and-Execute 范式的 PR Review 编排。

本包是 ReviewMind 的「真 Agent」编排层，替代 graph 包的硬编码流水线。
当前为渐进式接入：通过环境变量 REVIEW_USE_AGENT_LOOP 控制是否启用。

模块组成：
- schemas.py   : 三层流转的数据契约（ContextSnapshot/ReviewPlan/...）
- tools.py     : Tool 抽象与注册表（LLM 可调用工具的标准契约）
- llm_driver.py: LLM 交互引擎（解析工具调用 / 最终答案 / 终止判断）

后续 PR 补充：
- planner.py   : PlannerAgent（ReAct 循环产出审查计划）
- executor.py  : Executor（按计划并行执行维度分析）
- finalizer.py : Finalizer（聚合 + 报告，复用现有确定性逻辑）
- orchestrator.py: ReviewOrchestrator（串联三层，对接 graph 入口）
"""

from app.agent_loop.llm_driver import AgentStep, LLMDriver
from app.agent_loop.schemas import (
    ContextSnapshot,
    DimensionResult,
    DimensionTask,
    ReviewDimension,
    ReviewPlan,
)
from app.agent_loop.tools import Tool, ToolCall, ToolRegistry, ToolResult

__all__ = [
    # schemas
    "ReviewDimension",
    "DimensionTask",
    "ReviewPlan",
    "DimensionResult",
    "ContextSnapshot",
    # tools
    "Tool",
    "ToolCall",
    "ToolResult",
    "ToolRegistry",
    # driver
    "AgentStep",
    "LLMDriver",
]
