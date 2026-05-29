from uuid import uuid4

from app.schemas.review import (
    CreateReviewJobRequest,
    CreateReviewJobResponse,
    ReviewJobStatus,
    ReviewReport,
)


class ReviewJobService:
    def create_job(self, request: CreateReviewJobRequest) -> CreateReviewJobResponse:
        job_id = f"rev_{uuid4().hex[:8]}"
        return CreateReviewJobResponse(
            job_id=job_id,
            status=ReviewJobStatus.pending,
            stream_url=f"/api/v1/review/stream/{job_id}",
        )

    def get_report(self, job_id: str) -> ReviewReport:
        return ReviewReport(
            job_id=job_id,
            status=ReviewJobStatus.completed,
            summary="ReviewMind 骨架已创建。真实 PR 拉取、Diff 解析和多 Agent 审查将在后续 PR 中接入。",
            risk_level="LOW",
            findings=[],
            review_comment="## AI Review Summary\n\n当前为骨架占位报告，暂无真实风险发现。",
        )


review_job_service = ReviewJobService()