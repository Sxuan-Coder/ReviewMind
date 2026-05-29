import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.common import ApiResponse, success_response
from app.schemas.github import GitHubPullRequestRef
from app.schemas.review import (
    CreateReviewJobRequest,
    CreateReviewJobResponse,
    JobListResponse,
    ReviewJobDetailResponse,
    ReviewJobSnapshot,
)
from app.services.github_client import GitHubClient
from app.services.github_url_parser import GitHubPullRequestUrlError, parse_github_pr_url
from app.services.review_job_service import review_job_service

review_router = APIRouter(prefix="/review", tags=["review"])
github_router = APIRouter(prefix="/github", tags=["github"])

github_client = GitHubClient()


# --- Review Job 接口 ---

@review_router.post("/jobs", response_model=ApiResponse[CreateReviewJobResponse])
async def create_review_job(request: CreateReviewJobRequest) -> ApiResponse[CreateReviewJobResponse]:
    return success_response(
        await review_job_service.create_job(request),
        message="review job created",
        code=20200,
    )


@review_router.get("/jobs", response_model=ApiResponse[JobListResponse])
async def list_review_jobs(page: int = 1, page_size: int = 10) -> ApiResponse[JobListResponse]:
    return success_response(review_job_service.get_job_list(page, page_size))


@review_router.get("/jobs/{job_id}", response_model=ApiResponse[ReviewJobDetailResponse])
async def get_review_job_detail(job_id: str) -> ApiResponse[ReviewJobDetailResponse]:
    return success_response(review_job_service.get_job_detail(job_id))


@review_router.get("/jobs/{job_id}/state", response_model=ReviewJobSnapshot)
async def get_review_job_state(job_id: str) -> ReviewJobSnapshot:
    return review_job_service.get_job(job_id)


@review_router.post("/jobs/{job_id}/cancel", response_model=ApiResponse[ReviewJobDetailResponse])
async def cancel_review_job(job_id: str) -> ApiResponse[ReviewJobDetailResponse]:
    return success_response(
        review_job_service.cancel_job(job_id),
        message="review job cancelled",
    )


@review_router.get("/stream/{job_id}")
async def stream_review_progress(job_id: str) -> StreamingResponse:
    job = review_job_service.get_job(job_id)

    async def event_stream() -> AsyncIterator[str]:
        for event in job.progress_events:
            event_type = str(event.get("type", "progress"))
            data = _format_event_data(event_type, event)
            yield _format_sse(event_type, data)

        if job.status == "failed":
            warning_data = {
                "code": "JOB_FAILED",
                "message": job.error_message or "Review Job 执行失败",
            }
            yield _format_sse("warning", warning_data)

        if job.status in {"completed", "failed"}:
            done_data = {
                "job_id": job_id,
                "status": job.status,
                "report_url": f"/api/v1/review/jobs/{job_id}",
                "total_findings": _count_findings(job),
                "duration_ms": _calc_duration_ms(job),
            }
            yield _format_sse("done", done_data)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _format_event_data(event_type: str, event: dict[str, object]) -> dict[str, object]:
    if event_type == "progress":
        return {"step": event.get("step", ""), "percent": event.get("percent", 0), "message": event.get("message", "")}
    if event_type == "finding":
        finding_keys = {"id", "agent", "file", "line", "symbol", "level", "type", "confidence", "description", "suggestion"}
        return {k: v for k, v in event.items() if k in finding_keys}
    if event_type == "chunk":
        return {"target": event.get("target", "summary"), "content": event.get("content", "")}
    if event_type == "warning":
        return {"code": event.get("step", "WARNING"), "message": event.get("message", ""), "file": event.get("file")}
    return event


def _count_findings(job: ReviewJobSnapshot) -> int:
    if hasattr(job, "pipeline_result") and job.pipeline_result:
        pass
    return 0


def _calc_duration_ms(job: ReviewJobSnapshot) -> int:
    if job.created_at and hasattr(job, "updated_at") and job.updated_at:
        delta = job.updated_at - job.created_at
        return int(delta.total_seconds() * 1000)
    return 0


def _format_sse(event_type: str, payload: dict[str, object]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


# --- GitHub 辅助接口 ---

@github_router.post("/parse-pr-url", response_model=ApiResponse[GitHubPullRequestRef])
async def parse_pr_url(body: dict) -> ApiResponse[GitHubPullRequestRef]:
    pr_url = body.get("pr_url")
    if not pr_url:
        return success_response(None, message="pr_url is required", code=40000)
    try:
        ref = parse_github_pr_url(pr_url)
    except GitHubPullRequestUrlError as exc:
        return success_response(None, message=str(exc), code=40001)
    return success_response(ref)


@github_router.post("/pr-preview", response_model=ApiResponse[dict])
async def pr_preview(body: dict) -> ApiResponse[dict]:
    pr_url = body.get("pr_url")
    if not pr_url:
        return success_response(None, message="pr_url is required", code=40000)
    try:
        ref = parse_github_pr_url(pr_url)
    except GitHubPullRequestUrlError as exc:
        return success_response(None, message=str(exc), code=40001)
    pr_info = await github_client.fetch_pull_request(ref)
    files = await github_client.fetch_pull_request_files(ref)
    pr_data = {
        "owner": pr_info.owner,
        "repo": pr_info.repo,
        "number": pr_info.pull_number,
        "title": pr_info.title,
        "author": pr_info.author,
        "base_branch": pr_info.base.ref,
        "head_branch": pr_info.head.ref,
        "changed_files": pr_info.changed_files,
        "additions": pr_info.additions,
        "deletions": pr_info.deletions,
        "html_url": str(pr_info.html_url),
    }
    return success_response({
        "pr": pr_data,
        "files": [f.model_dump(mode="json") for f in files],
    })
