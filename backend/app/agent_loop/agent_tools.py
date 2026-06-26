"""Agent Loop 工具实现：把现有 service 能力封装为 LLM 可调用的 Tool。

两类工具：

1. Planner 探查工具（只读、轻量）—— 让 Planner 在产出审查计划前「看清」PR：
   - ``get_pr_overview`` : PR 标题/作者/规模等元信息
   - ``list_changed_files``: 变更文件清单与各自规模
   - ``detect_tech_stack`` : 已检测到的技术栈框架（来自预处理快照）

2. Executor 执行工具 —— Planner 产出计划后，Executor 调用它跑各维度：
   - ``analyze_dimension``: 按维度名调用对应 agent（复用现有 agents 包）
   - ``cross_validate``   : 对 finding 做技术栈误报校验（复用 finding_validator 规则）

设计要点：
- 工具操作的是 ``ContextSnapshot``（预处理层产出的只读快照），而非重新拉网络。
  这让 Planner 的决策基于已经拿到的真实数据，且无需在 Loop 内重复 I/O。
- 工具是无状态的：通过构造函数注入 snapshot / github_client，便于测试时替换。
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from app.agent_loop.schemas import ContextSnapshot, ReviewDimension
from app.agent_loop.tools import Tool, ToolRegistry
from app.agents import (
    performance_agent,
    security_agent,
    summary_agent,
    test_agent,
)
from app.schemas.agents import AgentContext, AgentFindingsResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Planner 探查工具（只读）
# ---------------------------------------------------------------------------


class GetPrOverviewArgs(BaseModel):
    """无参数工具：返回当前 PR 的概览。"""


class GetPrOverviewTool(Tool[GetPrOverviewArgs]):
    """返回 PR 的标题、作者、变更规模等元信息。"""

    name = "get_pr_overview"
    description = (
        "获取当前 PR 的概览信息：标题、作者、变更文件数、增删行数。"
        "用于在制定审查计划前了解 PR 的整体规模。"
    )
    args_model = GetPrOverviewArgs

    def __init__(self, snapshot: ContextSnapshot) -> None:
        self._snapshot = snapshot

    async def _run(self, args: GetPrOverviewArgs) -> dict[str, Any]:  # noqa: ARG002
        info = self._snapshot.pr_info or {}
        included = self._snapshot.filtered_files.get("included_files", [])
        total_add = sum(int(f.get("additions", 0)) for f in included if isinstance(f, dict))
        total_del = sum(int(f.get("deletions", 0)) for f in included if isinstance(f, dict))
        return {
            "title": info.get("title", ""),
            "author": info.get("author", ""),
            "state": info.get("state", ""),
            "changed_files": len(included),
            "additions": total_add,
            "deletions": total_del,
            "tech_stack_prompt": self._snapshot.tech_stack_prompt[:200],
        }


class ListChangedFilesArgs(BaseModel):
    limit: int = Field(default=20, description="最多返回的文件数量，默认 20")


class ListChangedFilesTool(Tool[ListChangedFilesArgs]):
    """列出变更文件清单（经 DiffFilter 过滤后的）。"""

    name = "list_changed_files"
    description = (
        "列出本次 PR 中经降噪过滤后的变更文件清单（文件名、状态、增删行数）。"
        "用于判断哪些文件/模块受影响，从而决定需要哪些审查维度。"
    )
    args_model = ListChangedFilesArgs

    def __init__(self, snapshot: ContextSnapshot) -> None:
        self._snapshot = snapshot

    async def _run(self, args: ListChangedFilesArgs) -> dict[str, Any]:
        included = self._snapshot.filtered_files.get("included_files", [])
        files = [
            {
                "filename": f.get("filename", ""),
                "status": f.get("status", "modified"),
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
            }
            for f in included
            if isinstance(f, dict)
        ]
        return {"total": len(files), "files": files[: args.limit]}


class DetectTechStackArgs(BaseModel):
    """无参数工具：返回已检测到的技术栈。"""


class DetectTechStackTool(Tool[DetectTechStackArgs]):
    """返回预处理阶段检测到的技术栈框架（来自 snapshot）。"""

    name = "detect_tech_stack"
    description = (
        "返回本次 PR 检测到的项目技术栈与框架（如 React / Django / SQLAlchemy）。"
        "用于判断哪些安全检查在该技术栈下可能是误报（如 React 的 XSS）。"
    )
    args_model = DetectTechStackArgs

    def __init__(self, snapshot: ContextSnapshot) -> None:
        self._snapshot = snapshot

    async def _run(self, args: DetectTechStackArgs) -> dict[str, Any]:  # noqa: ARG002
        prompt = self._snapshot.tech_stack_prompt or ""
        return {"detected": bool(prompt), "tech_stack_context": prompt[:500]}


# ---------------------------------------------------------------------------
# Executor 执行工具
# ---------------------------------------------------------------------------


class AnalyzeDimensionArgs(BaseModel):
    dimension: ReviewDimension = Field(description="要执行的审查维度")
    use_rag: bool = Field(default=False, description="是否注入 RAG 上下文")


# 维度 → agent 模块的映射（复用现有 agents 包）
_DIMENSION_AGENTS = {
    ReviewDimension.SUMMARY: summary_agent,
    ReviewDimension.SECURITY: security_agent,
    ReviewDimension.PERFORMANCE: performance_agent,
    ReviewDimension.TEST: test_agent,
}


class AnalyzeDimensionTool(Tool[AnalyzeDimensionArgs]):
    """按维度名执行对应审查 Agent（复用现有 agents 包的 run_async）。

    这是 Executor 的核心工具：Planner 计划里每个维度任务，对应一次本工具调用。
    """

    name = "analyze_dimension"
    description = (
        "执行指定维度的代码审查（summary/security/performance/test）。"
        "返回该维度的 findings 列表。Executor 按计划对每个维度调用一次。"
    )
    args_model = AnalyzeDimensionArgs

    def __init__(self, snapshot: ContextSnapshot) -> None:
        self._snapshot = snapshot

    async def _run(self, args: AnalyzeDimensionArgs) -> dict[str, Any]:
        agent_mod = _DIMENSION_AGENTS.get(args.dimension)
        if agent_mod is None:
            return {"dimension": args.dimension.value, "ok": False, "error": "unknown dimension"}

        # 复用现有的 AgentContext 构造方式（与 graph/nodes.py 一致）
        ctx = AgentContext(
            pr_info=self._snapshot.pr_info,
            parsed_diff=self._snapshot.parsed_diff,
            ast_contexts=self._snapshot.ast_contexts,
            rag_contexts=self._snapshot.rag_contexts if args.use_rag else [],
            tech_stack_prompt=self._snapshot.tech_stack_prompt,
        )
        result: AgentFindingsResult = await agent_mod.run_async(ctx)
        return {
            "dimension": args.dimension.value,
            "ok": True,
            "summary": result.summary,
            "findings_count": len(result.findings),
            # findings 保留完整结构，供 Finalizer 聚合（这里只回传计数给 LLM 看）
            "_result": result.model_dump(mode="json"),
        }


class CrossValidateArgs(BaseModel):
    """单条 finding 的误报校验参数。

    为保持工具无状态且可被 LLM 调用，这里用基础字段描述 finding。
    """

    finding_type: str = Field(description="finding 的类型，如 sql_injection / xss")
    file: str = Field(description="finding 所在文件路径")


class CrossValidateTool(Tool[CrossValidateArgs]):
    """基于技术栈判断单条 finding 是否为误报（复用 finding_validator 规则）。"""

    name = "cross_validate"
    description = (
        "基于项目技术栈判断某条 finding 是否为误报。"
        "例如对 React 项目的 .tsx 文件报告 XSS，会被判定为误报。"
    )
    args_model = CrossValidateArgs

    def __init__(self, snapshot: ContextSnapshot) -> None:
        self._snapshot = snapshot

    async def _run(self, args: CrossValidateArgs) -> dict[str, Any]:
        # 复用 graph/nodes.py 中 _is_false_positive 的同等规则
        from app.graph.nodes import _is_false_positive

        # 构造一个轻量 finding-like 对象供规则函数判断
        class _LiteFinding:
            def __init__(self, ftype: str, ffile: str) -> None:
                self.type = ftype
                self.file = ffile

        is_fp = _is_false_positive(
            _LiteFinding(args.finding_type, args.file),
            self._snapshot.tech_stack_prompt,
        )
        return {
            "is_false_positive": is_fp,
            "finding_type": args.finding_type,
            "file": args.file,
            "verdict": "误报，建议丢弃" if is_fp else "有效，保留",
        }


# ---------------------------------------------------------------------------
# 注册表工厂
# ---------------------------------------------------------------------------


def build_planner_registry(snapshot: ContextSnapshot) -> ToolRegistry:
    """构建 Planner 用的工具注册表（只读探查工具）。"""
    reg = ToolRegistry()
    reg.register(GetPrOverviewTool(snapshot))
    reg.register(ListChangedFilesTool(snapshot))
    reg.register(DetectTechStackTool(snapshot))
    return reg


def build_executor_registry(snapshot: ContextSnapshot) -> ToolRegistry:
    """构建 Executor 用的工具注册表（执行工具）。"""
    reg = ToolRegistry()
    reg.register(AnalyzeDimensionTool(snapshot))
    reg.register(CrossValidateTool(snapshot))
    return reg
