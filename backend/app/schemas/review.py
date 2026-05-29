from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class ReviewJobStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


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
    report_url: str


class ReviewFinding(BaseModel):
    id: str
    agent: str
    file: str
    line: int
    level: str
    type: str
    confidence: float
    description: str
    suggestion: str
    symbol: str | None = None
    code_snippet: str | None = None


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
    pipeline_result: dict[str, Any] | None = None


# --- 报告相关结构 ---

class PrInfo(BaseModel):
    owner: str
    repo: str
    number: int
    title: str
    author: str
    base_branch: str
    head_branch: str
    html_url: str


class ReviewReportStats(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    suggestion: int = 0


class ChangedFile(BaseModel):
    filename: str
    status: str
    additions: int = 0
    deletions: int = 0
    risk_count: int = 0


class ChangedSymbol(BaseModel):
    file: str
    symbol: str
    language: str
    start_line: int
    end_line: int
    changed_lines: list[int] = Field(default_factory=list)


class ReviewReport(BaseModel):
    summary: str
    risk_level: str
    stats: ReviewReportStats = Field(default_factory=ReviewReportStats)
    changed_files: list[ChangedFile] = Field(default_factory=list)
    changed_symbols: list[ChangedSymbol] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    review_comment: str = ""


class ReviewJobDetailResponse(BaseModel):
    job_id: str
    status: ReviewJobStatus
    pr: PrInfo | None = None
    progress: ReviewProgressEvent | None = None
    findings: list[ReviewFinding] = Field(default_factory=list)
    report: ReviewReport | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None