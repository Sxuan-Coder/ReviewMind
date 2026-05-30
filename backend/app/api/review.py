import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
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
from app.models.review_job import _QUEUE_DONE
from app.services.review_job_service import review_job_service
from app.services.review_job_store import ReviewJobNotFoundError, review_job_store

review_router = APIRouter(prefix="/review", tags=["review"])
github_router = APIRouter(prefix="/github", tags=["github"])

github_client = GitHubClient()

# SSE 心跳间隔（秒）
SSE_HEARTBEAT_SECONDS = 15
# SSE 队列读取超时（秒），到时间就发心跳
SSE_QUEUE_TIMEOUT_SECONDS = 5


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
    """SSE 实时进度流。

    从 job 的异步事件队列读取事件并推送给前端。
    支持心跳保活和优雅断开。
    """
    try:
        job = review_job_store.get(job_id)  # 获取原始 ReviewJob（含 event_queue）
    except ReviewJobNotFoundError:
        # 返回 SSE 格式的错误事件，而不是 HTTP 404
        async def error_stream() -> AsyncIterator[str]:
            error_data = {"code": "JOB_NOT_FOUND", "message": f"Review job not found: {job_id}"}
            yield _format_sse("error", error_data)
            done_data = {"job_id": job_id, "status": "error", "message": "Job not found"}
            yield _format_sse("done", done_data)

        return StreamingResponse(error_stream(), media_type="text/event-stream")

    event_queue = job.event_queue

    async def event_stream() -> AsyncIterator[str]:
        # 先发送已收集的历史事件
        history_count = len(job.progress_events)
        for event in job.progress_events:
            event_type = str(event.get("type", "progress"))
            data = _format_event_data(event_type, event)
            yield _format_sse(event_type, data)

        # 如果任务已经结束，直接发送 done 并退出
        if job.status in {"completed", "failed", "cancelled"}:
            done_data = _build_done_data(job_id, job.status, job.error_message)
            yield _format_sse("done", done_data)
            return

        # 实时等待新事件（跳过已在历史中发送的事件）
        last_heartbeat = 0.0
        loop = asyncio.get_event_loop()
        skipped = 0  # 已跳过的队列事件数

        while True:
            try:
                item = await asyncio.wait_for(event_queue.get(), timeout=SSE_QUEUE_TIMEOUT_SECONDS)

                # 跳过队列中已有的历史事件
                if skipped < history_count:
                    skipped += 1
                    continue

                # 检查是否是结束信号
                if item is _QUEUE_DONE:
                    break

                if isinstance(item, dict):
                    event_type = str(item.get("type", "progress"))
                    data = _format_event_data(event_type, item)
                    yield _format_sse(event_type, data)

            except asyncio.TimeoutError:
                # 超时 → 发送心跳注释
                now = loop.time()
                if now - last_heartbeat >= SSE_HEARTBEAT_SECONDS:
                    yield ": heartbeat\n\n"
                    last_heartbeat = now

        # 循环结束 → 发送 done
        # 重新读取 job 状态（可能已被更新）
        try:
            current_job = review_job_store.get(job_id)
            final_status = current_job.status
            error_msg = current_job.error_message
        except ReviewJobNotFoundError:
            final_status = "unknown"
            error_msg = None

        done_data = _build_done_data(job_id, final_status, error_msg)
        yield _format_sse("done", done_data)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )


def _build_done_data(job_id: str, status: str, error_message: str | None = None) -> dict:
    return {
        "job_id": job_id,
        "status": status,
        "report_url": f"/api/v1/review/jobs/{job_id}",
        "error_message": error_message,
    }


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
