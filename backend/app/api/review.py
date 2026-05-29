import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.common import ApiResponse, success_response
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
    async def event_stream() -> AsyncIterator[str]:
        steps = [
            ("FETCH_PR", 10, "等待接入 GitHub PR 拉取模块"),
            ("DIFF_FILTER", 25, "等待接入 DiffFilter 降噪模块"),
            ("AST_CONTEXT", 45, "等待接入 AST 方法级上下文模块"),
            ("AGENT_REVIEW", 70, "等待接入 LangGraph 多 Agent 工作流"),
            ("REPORT", 100, "骨架占位分析完成"),
        ]
        for step, percent, message in steps:
            payload = {"job_id": job_id, "step": step, "percent": percent, "message": message}
            yield f"event: progress\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.2)
        yield f"event: done\ndata: {json.dumps({'job_id': job_id, 'status': 'completed'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")