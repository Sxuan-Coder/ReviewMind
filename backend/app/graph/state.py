from dataclasses import dataclass, field
from typing import Any

from app.schemas.agents import AggregatedRisk, ReviewReportOutput


@dataclass
class ReviewGraphState:
    """LangGraph-style 状态对象，各节点读写同一状态。"""

    job_id: str
    pr_url: str

    # fetch_pr 输出
    pr_info: dict[str, Any] = field(default_factory=dict)

    # fetch_files 输出
    github_files: list[dict[str, Any]] = field(default_factory=list)

    # diff_filter 输出
    filtered_files: dict[str, Any] = field(default_factory=dict)

    # parse_diff 输出
    parsed_diff: list[dict[str, Any]] = field(default_factory=list)

    # ast_context 输出
    ast_contexts: list[dict[str, Any]] = field(default_factory=list)

    # rag_context 输出
    rag_level: int = 0                     # RagTriggerLevel 值
    rag_trigger_reason: str = ""           # 触发原因摘要
    rag_contexts: list[dict[str, Any]] = field(default_factory=list)  # 检索到的相似代码

    # 审查配置
    config: dict[str, Any] = field(default_factory=dict)

    # agents 输出
    summary_text: str = ""
    agent_results: list[Any] = field(default_factory=list)

    # risk_judge 输出
    aggregated_risk: AggregatedRisk | None = None

    # report_agent 输出
    report_output: ReviewReportOutput | None = None

    # pipeline_result 最终结果
    pipeline_result: dict[str, Any] = field(default_factory=dict)

    # 错误 / 警告
    error: str | None = None
    warnings: list[str] = field(default_factory=list)