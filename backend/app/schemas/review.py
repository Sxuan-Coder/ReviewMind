from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class ReviewJobStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ReviewConfig(BaseModel):
    enable_ast: bool = True
    enable_rag: bool = False
    strict_mode: bool = True


class CreateReviewJobRequest(BaseModel):
    pr_url: HttpUrl = Field(description="GitHub Pull Request URL")
    config: ReviewConfig = Field(default_factory=ReviewConfig)


class CreateReviewJobResponse(BaseModel):
    job_id: str
    status: ReviewJobStatus
    stream_url: str


class ReviewFinding(BaseModel):
    agent: str
    file: str
    line: int
    level: str
    type: str
    confidence: float
    description: str
    suggestion: str


class ReviewProgressEvent(BaseModel):
    step: str
    percent: int = Field(ge=0, le=100)
    message: str
    type: str = "progress"


class ReviewJobSnapshot(BaseModel):
    job_id: str
    pr_url: HttpUrl
    status: ReviewJobStatus
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None
    progress_events: list[dict[str, Any]] = Field(default_factory=list)


class ReviewReport(BaseModel):
    job_id: str
    status: ReviewJobStatus
    summary: str
    risk_level: str
    findings: list[ReviewFinding]
    review_comment: str