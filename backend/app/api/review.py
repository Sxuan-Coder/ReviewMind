import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.common import ApiResponse, success_response
from app.schemas.events import ReviewEventType, ReviewStreamEvent
from app.schemas.github import GitHubPullRequestRef
from app.schemas.review import (
    CreateReviewJobRequest,
    CreateReviewJobResponse,
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
            stream_event = _to_stream_event(job_id, event)
            yield _format_sse(stream_event.type, stream_event.model_dump(mode="json"))

        if job.status == "failed":
            warning = ReviewStreamEvent(
                type=ReviewEventType.warning,
                job_id=job_id,
                step="JOB_FAILED",
                percent=100,
                message=job.error_message or "Review Job 执行失败",
            )
            yield _format_sse(ReviewEventType.warning, warning.model_dump(mode="json"))

        if job.status in {"completed", "failed"}:
            done = ReviewStreamEvent(
                type=ReviewEventType.done,
                job_id=job_id,
                step="JOB_DONE",
                percent=100,
                message="Review Job 已结束",
                payload={"status": job.status},
            )
            yield _format_sse(ReviewEventType.done, done.model_dump(mode="json"))

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _to_stream_event(job_id: str, event: dict[str, object]) -> ReviewStreamEvent:
    event_type = ReviewEventType(str(event.get("type", ReviewEventType.progress)))
    return ReviewStreamEvent(
        type=event_type,
        job_id=job_id,
        step=str(event.get("step", "UNKNOWN")),
        percent=int(event.get("percent", 0)),
        message=str(event.get("message", "")),
        payload={key: value for key, value in event.items() if key not in {"type", "step", "percent", "message"}},
    )


def _format_sse(event_type: ReviewEventType, payload: dict[str, object]) -> str:
    return f"event: {event_type.value}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


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
    return success_response({
        "pr": pr_info.model_dump(mode="json"),
        "files": [f.model_dump(mode="json") for f in files],
    })