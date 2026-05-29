from dataclasses import dataclass
from typing import Any

from app.models.review_job import ReviewJob
from app.schemas.diff import PullRequestFile
from app.schemas.github import GitHubPullRequestFile
from app.schemas.review import ReviewJobStatus, ReviewReport
from app.services.diff_filter import filter_diff_files
from app.services.diff_parser import parse_diff_file
from app.services.github_client import GitHubClient
from app.services.github_url_parser import parse_github_pr_url
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
        try:
            self._store.update_status(job.job_id, ReviewJobStatus.running)
            self._add_progress(job.job_id, "PARSE_PR_URL", 10, "GitHub PR URL 已解析")

            pr_ref = parse_github_pr_url(job.pr_url)
            pr_info = await self._github_client.fetch_pull_request(pr_ref)
            self._add_progress(job.job_id, "FETCH_PR", 30, "GitHub PR 基本信息已拉取")

            github_files = await self._github_client.fetch_pull_request_files(pr_ref)
            pull_request_files = [_to_pull_request_file(file) for file in github_files]
            self._add_progress(job.job_id, "FETCH_FILES", 45, "GitHub PR 文件列表已拉取")

            filtered = filter_diff_files(pull_request_files)
            self._add_progress(job.job_id, "DIFF_FILTER", 65, "Diff 降噪已完成")

            parsed_diff = [parse_diff_file(file) for file in filtered.included_files]
            self._add_progress(job.job_id, "DIFF_PARSE", 85, "Diff 变更行解析已完成")

            result = ReviewPipelineResult(
                pr_info=pr_info.model_dump(mode="json"),
                filtered_files=filtered.model_dump(mode="json"),
                parsed_diff=[item.model_dump(mode="json") for item in parsed_diff],
            )
            self._store.save_pipeline_result(job.job_id, result)

            report = ReviewReport(
                job_id=job.job_id,
                status=ReviewJobStatus.completed,
                summary=f"已完成 PR #{pr_info.pull_number} 的基础 Diff 分析，共保留 {len(filtered.included_files)} 个文件。",
                risk_level="LOW",
                findings=[],
                review_comment="## AI Review Summary\n\n基础 Review Pipeline 已完成，后续 PR 将接入 Mock Agents 和风险聚合。",
            )
            self._store.update_status(job.job_id, ReviewJobStatus.completed, report=report)
            self._add_progress(job.job_id, "PIPELINE_DONE", 100, "Review Pipeline 已完成")
            return result
        except Exception as exc:
            self._store.update_status(job.job_id, ReviewJobStatus.failed, error_message=str(exc))
            self._store.add_progress_event(
                job.job_id,
                {"type": "warning", "step": "PIPELINE_FAILED", "percent": 100, "message": str(exc)},
            )
            return ReviewPipelineResult(pr_info={}, filtered_files={}, parsed_diff=[])

    def _add_progress(self, job_id: str, step: str, percent: int, message: str) -> None:
        self._store.add_progress_event(
            job_id,
            {"type": "progress", "step": step, "percent": percent, "message": message},
        )


def _to_pull_request_file(file: GitHubPullRequestFile) -> PullRequestFile:
    return PullRequestFile(
        filename=file.filename,
        status=file.status,
        additions=file.additions,
        deletions=file.deletions,
        patch=file.patch,
    )