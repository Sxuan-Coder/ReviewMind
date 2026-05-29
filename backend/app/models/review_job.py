from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.schemas.review import ReviewJobStatus, ReviewReport


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

    def mark_updated(self) -> None:
        self.updated_at = datetime.now(UTC)

    def mark_completed(self) -> None:
        self.completed_at = datetime.now(UTC)
        self.mark_updated()
