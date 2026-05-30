"""ReviewPipeline：委托 ReviewGraph 执行完整的 AI Review 工作流。

工作流节点顺序：
    fetch_pr → fetch_files → diff_filter → parse_diff → ast_context
    → summary_agent → security_agent → performance_agent → test_agent
    → risk_judge → report_agent

每个节点由 ReviewGraph 编排，自动推送 progress/finding/chunk 等 SSE 事件。
ReviewPipeline 只负责创建 Graph 实例并等待结果。
"""

import json
from dataclasses import dataclass
from typing import Any

from app.graph.review_graph import ReviewGraph
from app.models.review_job import ReviewJob
from app.services.github_client import GitHubClient
from app.services.review_job_store import ReviewJobStore


@dataclass(frozen=True)
class ReviewPipelineResult:
    pr_info: dict[str, Any]
    filtered_files: dict[str, Any]
    parsed_diff: list[dict[str, Any]]


class ReviewPipeline:
    def __init__(self, store: ReviewJobStore, github_client: GitHubClient | None = None) -> None:
        self._store = store
        self._github_client = github_client or GitHubClient()

    async def run(self, job: ReviewJob) -> ReviewPipelineResult:
        """委托 ReviewGraph 执行完整的多 Agent + LLM Review 工作流。

        ReviewGraph 负责：
        1. 编排 11 个节点的有序执行
        2. 推送 progress/chunk/finding SSE 事件
        3. Agent 调用 LLM 进行 AI 分析
        4. Risk Judge 聚合 + Report Agent 生成最终报告
        5. 容错：非关键节点失败降级，关键节点失败标记 failed
        """
        graph = ReviewGraph(self._store, self._github_client)
        result = await graph.run(job)

        # SSE 推送文件列表（供前端实时展示）
        included = result.filtered_files.get("included_files", [])
        file_names = [
            f.get("filename", f.get("file", "unknown")) if isinstance(f, dict) else getattr(f, "filename", "unknown")
            for f in included
        ]
        if file_names:
            self._store.add_progress_event(
                job.job_id,
                {
                    "type": "chunk",
                    "target": "files",
                    "content": json.dumps(file_names, ensure_ascii=False),
                },
            )

        return ReviewPipelineResult(
            pr_info=result.pr_info,
            filtered_files=result.filtered_files,
            parsed_diff=result.parsed_diff,
        )
