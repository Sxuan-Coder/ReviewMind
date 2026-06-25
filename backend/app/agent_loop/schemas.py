"""Agent Loop 内部数据契约。

本模块定义 ReviewOrchestrator 三层（Planner → Executor → Finalizer）
之间流转的数据结构，是 Agent Loop 的「骨架」。本文件只包含数据定义，
不包含任何 LLM 调用或副作用逻辑，便于单独单测。
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.agents import AgentFindingsResult


class ReviewDimension(str, Enum):
    """Planner 可调度的审查维度。

    值与现有 agents 包一一对应，Executor 通过此枚举路由到对应 agent。
    """

    SUMMARY = "summary"
    SECURITY = "security"
    PERFORMANCE = "performance"
    TEST = "test"


class DimensionTask(BaseModel):
    """Planner 产出计划中的单个维度任务。"""

    dimension: ReviewDimension
    # 该维度是否需要 RAG 上下文（由 Planner 根据风险判断）
    use_rag: bool = False
    # 该维度是否允许在 diff 不足时主动拉取完整文件
    allow_fetch_full_file: bool = False
    # Planner 给该维度的审查理由（可读，便于调试与日志）
    rationale: str = ""


class ReviewPlan(BaseModel):
    """Planner 的输出：本轮 Review 的执行计划。"""

    dimensions: list[DimensionTask] = Field(default_factory=list)
    # 整体风险判断（供 Finalizer 参考，非强制）
    overall_risk_hint: str = ""
    # Planner 自述的推理摘要（可读）
    reasoning: str = ""

    def dimension_names(self) -> list[str]:
        return [d.dimension.value for d in self.dimensions]


class DimensionResult(BaseModel):
    """Executor 单个维度执行的产出。"""

    dimension: ReviewDimension
    # 包装现有 agent 的 AgentFindingsResult（可能为空，表示该维度无产出/降级）
    result: AgentFindingsResult | None = None
    success: bool = True
    # 失败或降级时的原因
    error: str = ""


class ContextSnapshot(BaseModel):
    """预处理层（确定性）产出的、供 Planner 和 Executor 共享的上下文快照。

    由 ReviewOrchestrator 在跑完预处理节点后填充，是 Agent Loop 的输入。
    刻意保持为只读快照：Planner 据此决策，Executor 据此执行。
    """

    job_id: str
    pr_url: str
    pr_info: dict[str, Any] = Field(default_factory=dict)
    # 经 diff_filter 过滤后的结构化文件
    filtered_files: dict[str, Any] = Field(default_factory=dict)
    # 解析后的 diff（含 changed_lines）
    parsed_diff: list[dict[str, Any]] = Field(default_factory=list)
    # AST 方法级上下文
    ast_contexts: list[dict[str, Any]] = Field(default_factory=list)
    # RAG 检索到的相似代码（可能为空）
    rag_contexts: list[dict[str, Any]] = Field(default_factory=list)
    # 技术栈框架安全上下文 prompt
    tech_stack_prompt: str = ""
    # 运行配置
    config: dict[str, Any] = Field(default_factory=dict)
