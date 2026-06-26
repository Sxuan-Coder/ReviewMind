"""Finalizer：聚合各维度结果，生成最终报告。

职责（确定性，不调 LLM）：
1. 收集所有 DimensionResult 中的 AgentFindingsResult；
2. 复用 finding_validator 规则，过滤基于技术栈的明显误报；
3. 复用 risk_judge_agent.aggregate 去重 + 计算风险等级；
4. 复用 report_agent.generate_report 生成结构化报告。

为什么 Finalizer 是确定性的？
仲裁（去重、置信度排序）和报告生成本就不需要 LLM 的创造性，用确定性逻辑能
保证结果稳定可复现——同一份 PR 两次审查得到相同结论。这与「决策用 LLM、
执行用并行、聚合用规则」的分层设计一致，也避免了 LLM 在仲裁环节的随机性。

本模块产出的 ``FinalizedReport`` 是 Agent Loop 的最终产出，结构与现有
graph/nodes.py 中 _finish 组装的 ReviewReport 对齐，便于 orchestrator 适配。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.agent_loop.schemas import ContextSnapshot, DimensionResult
from app.agents import report_agent, risk_judge_agent
from app.schemas.agents import AgentFindingsResult, AggregatedRisk, ReviewReportOutput

logger = logging.getLogger(__name__)


@dataclass
class FinalizedReport:
    """Agent Loop 的最终聚合产出。"""

    aggregated_risk: AggregatedRisk
    report_output: ReviewReportOutput
    summary_text: str
    # 被误报规则丢弃的 finding 数（供调试/统计）
    findings_dropped: int


class Finalizer:
    """聚合维度结果 + 生成报告（确定性）。"""

    def __init__(self, snapshot: ContextSnapshot) -> None:
        self._snapshot = snapshot

    def finalize(self, dimension_results: list[DimensionResult], job_id: str) -> FinalizedReport:
        """聚合所有维度结果，返回最终报告。"""
        # 1. 收集成功的 AgentFindingsResult
        agent_results: list[AgentFindingsResult] = []
        summary_text = ""
        for dr in dimension_results:
            if dr.result is None:
                continue
            agent_results.append(dr.result)
            # summary 维度的 summary 文本单独提取，供报告使用
            if dr.dimension.value == "summary" and dr.result.summary:
                summary_text = dr.result.summary

        # 2. 复用 finding_validator 规则过滤误报（与 graph/nodes.py 一致）
        findings_dropped = self._filter_false_positives(agent_results)

        # 3. 复用 risk_judge 聚合（去重 + 风险等级）
        aggregated_risk = risk_judge_agent.aggregate(agent_results)
        logger.info(
            "[FINALIZER] aggregated %d findings (dropped %d, dedup %d), risk=%s",
            len(aggregated_risk.findings), findings_dropped,
            aggregated_risk.dedup_count, aggregated_risk.risk_level,
        )

        # 4. 兜底 summary（若无 summary 维度或为空）
        if not summary_text:
            summary_text = f"PR 分析完成，共 {len(self._snapshot.parsed_diff)} 个文件。"

        # 5. 复用 report_agent 生成结构化报告
        report_output = report_agent.generate_report(job_id, aggregated_risk, summary_text)

        return FinalizedReport(
            aggregated_risk=aggregated_risk,
            report_output=report_output,
            summary_text=summary_text,
            findings_dropped=findings_dropped,
        )

    # ------------------------------------------------------------------
    # 误报过滤（复用 graph/nodes.py 的 _is_false_positive 规则）
    # ------------------------------------------------------------------

    def _filter_false_positives(self, agent_results: list[AgentFindingsResult]) -> int:
        """基于技术栈上下文过滤明显误报，返回被丢弃的数量。"""
        tech_stack_prompt = self._snapshot.tech_stack_prompt
        if not tech_stack_prompt:
            return 0

        from app.graph.nodes import _is_false_positive

        dropped = 0
        for result in agent_results:
            original = result.findings
            kept = []
            for f in original:
                if _is_false_positive(f, tech_stack_prompt):
                    dropped += 1
                    logger.info(
                        "[FINALIZER] dropped false positive: agent=%s file=%s type=%s",
                        f.agent, f.file, f.type,
                    )
                else:
                    kept.append(f)
            result.findings = kept
        return dropped
