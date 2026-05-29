from uuid import uuid4

from fastapi import HTTPException, status

from app.models.review_job import ReviewJob
from app.schemas.review import (
    CreateReviewJobRequest,
    CreateReviewJobResponse,
    ReviewJobDetailResponse,
    ReviewJobSnapshot,
    ReviewJobStatus,
    ReviewReport,
)
from app.services.review_job_store import ReviewJobNotFoundError, ReviewJobStore, review_job_store
from app.services.review_pipeline import ReviewPipeline


class ReviewJobService:
    def __init__(self, store: ReviewJobStore, pipeline: ReviewPipeline | None = None) -> None:
        self._store = store
        self._pipeline = pipeline or ReviewPipeline(store)

    async def create_job(self, request: CreateReviewJobRequest) -> CreateReviewJobResponse:
        job_id = f"rev_{uuid4().hex[:8]}"
        job = ReviewJob(job_id=job_id, pr_url=str(request.pr_url))
        self._store.create(job)
        self._store.add_progress_event(
            job_id,
            {"step": "JOB_CREATED", "percent": 0, "message": "Review Job 已创建"},
        )
        await self._pipeline.run(job)
        return CreateReviewJobResponse(
            job_id=job.job_id,
            status=self._store.get(job.job_id).status,
            stream_url=f"/api/v1/review/stream/{job.job_id}",
            report_url=f"/api/v1/review/jobs/{job.job_id}",
        )

    def get_job_detail(self, job_id: str) -> ReviewJobDetailResponse:
        """对齐文档 4.2：GET /review/jobs/{job_id} 的完整响应。"""
        job = self._get_job_or_404(job_id)

        # 构建 pr 信息
        pr_info = None
        if job.pr_info:
            pr_info = {
                "owner": job.pr_info.get("owner", ""),
                "repo": job.pr_info.get("repo", ""),
                "number": job.pr_info.get("pull_number", 0),
                "title": job.pr_info.get("title", ""),
                "author": job.pr_info.get("author", ""),
                "base_branch": job.pr_info.get("base", {}).get("ref", "") if isinstance(job.pr_info.get("base"), dict) else "",
                "head_branch": job.pr_info.get("head", {}).get("ref", "") if isinstance(job.pr_info.get("head"), dict) else "",
                "html_url": job.pr_info.get("html_url", ""),
            }

        # 最新进度
        progress = None
        if job.progress_events:
            last = job.progress_events[-1]
            progress = {
                "step": last.get("step", "UNKNOWN"),
                "percent": last.get("percent", 0),
                "message": last.get("message", ""),
                "type": last.get("type", "progress"),
            }

        return ReviewJobDetailResponse(
            job_id=job.job_id,
            status=job.status,
            pr=pr_info,
            progress=progress,
            findings=[f for f in (job.report.findings if job.report else [])],
            report=job.report,
            created_at=job.created_at,
            completed_at=job.completed_at,
        )

    def get_report(self, job_id: str) -> ReviewReport:
        """兼容旧接口调用，直接返回报告。"""
        job = self._get_job_or_404(job_id)
        if job.report is not None:
            return job.report

        return ReviewReport(
            summary="ReviewMind 已创建任务。真实 PR 拉取、Diff 解析和多 Agent 审查将在后续 PR 中接入。",
            risk_level="LOW",
            findings=[],
            review_comment="## AI Review Summary\n\n当前任务已进入内存状态仓库，暂无真实风险发现。",
        )

    def get_job(self, job_id: str) -> ReviewJobSnapshot:
        job = self._get_job_or_404(job_id)
        return ReviewJobSnapshot(
            job_id=job.job_id,
            pr_url=job.pr_url,
            status=job.status,
            created_at=job.created_at,
            updated_at=job.updated_at,
            error_message=job.error_message,
            progress_events=job.progress_events,
            pipeline_result=job.pipeline_result,
        )

    def cancel_job(self, job_id: str) -> ReviewJobDetailResponse:
        job = self._get_job_or_404(job_id)
        self._store.update_status(job_id, ReviewJobStatus.cancelled)
        return self.get_job_detail(job_id)

    def _get_job_or_404(self, job_id: str) -> ReviewJob:
        try:
            return self._store.get(job_id)
        except ReviewJobNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Review job not found: {job_id}",
            ) from exc


review_job_service = ReviewJobService(review_job_store)