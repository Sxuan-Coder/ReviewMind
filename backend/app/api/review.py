import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.common import ApiResponse, success_response
from app.schemas.events import ReviewEventType, ReviewStreamEvent
from app.schemas.review import CreateReviewJobRequest, CreateReviewJobResponse, ReviewJobSnapshot, ReviewReport
from app.services.review_job_service import review_job_service

router = APIRouter(prefix="/review", tags=["review"])


@router.post("/jobs", response_model=ApiResponse[CreateReviewJobResponse])
async def create_review_job(request: CreateReviewJobRequest) -> ApiResponse[CreateReviewJobResponse]:
    return success_response(
        await review_job_service.create_job(request),
        message="review job created",
        code=20200,
    )


@router.get("/jobs/{job_id}", response_model=ApiResponse[ReviewReport])
async def get_review_report(job_id: str) -> ApiResponse[ReviewReport]:
    return success_response(review_job_service.get_report(job_id))


@router.get("/jobs/{job_id}/state", response_model=ReviewJobSnapshot)
async def get_review_job_state(job_id: str) -> ReviewJobSnapshot:
    return review_job_service.get_job(job_id)


@router.get("/stream/{job_id}")
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
