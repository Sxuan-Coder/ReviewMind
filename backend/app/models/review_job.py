import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.schemas.review import ReviewJobStatus, ReviewReport

# 队列结束信号
_QUEUE_DONE = object()


@dataclass
class ReviewJob:
    job_id: str
    pr_url: str
    status: ReviewJobStatus = ReviewJobStatus.pending
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    error_message: str | None = None
    progress_events: list[dict[str, Any]] = field(default_factory=list)
    pipeline_result: dict[str, Any] | None = None
    report: ReviewReport | None = None
    pr_info: dict[str, Any] | None = None
    # SSE 实时推送队列（非 dataclass field，在 create_job 时注入）
    event_queue: Any = field(default=None, repr=False, compare=False)

    def mark_updated(self) -> None:
        self.updated_at = datetime.now(UTC)

    def mark_completed(self) -> None:
        self.completed_at = datetime.now(UTC)
        self.mark_updated()

    def push_event(self, event: dict[str, Any]) -> None:
        """将事件推入 SSE 队列（非阻塞），供实时流使用。"""
        if self.event_queue is not None:
            try:
                self.event_queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # 队列满了就丢弃，不影响主流程

    def signal_done(self) -> None:
        """通知 SSE 流任务已完成。"""
        if self.event_queue is not None:
            try:
                self.event_queue.put_nowait(_QUEUE_DONE)
            except asyncio.QueueFull:
                pass
