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


# --- 报告相关结构（与 API 文档对齐） ---

class PrInfo(BaseModel):
    owner: str
    repo: str
    number: int
    title: str
    author: str
    base_branch: str
    head_branch: str
    changed_files: int = 0
    additions: int = 0
    deletions: int = 0
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
    changes: int = 0
    patch: str | None = None
    risk_count: int = 0


class ChangedSymbol(BaseModel):
    file: str
    symbol: str
    language: str
    start_line: int
    end_line: int
    changed_lines: list[int] = Field(default_factory=list)
    code: str | None = None


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
    updated_at: datetime | None = None
    error_message: str | None = None


class JobListItem(BaseModel):
    job_id: str
    status: ReviewJobStatus
    pr_title: str = ""
    pr_url: str = ""
    risk_level: str = "LOW"
    finding_count: int = 0
    created_at: datetime | None = None


class JobListResponse(BaseModel):
    items: list[JobListItem] = Field(default_factory=list)
    page: int = 1
    page_size: int = 10
    total: int = 0


class PostCommentRequest(BaseModel):
    comment_body: str | None = Field(default=None, description="自定义评论内容，不传则使用 report.review_comment")


class PostCommentResponse(BaseModel):
    comment_id: int
    html_url: str


class MergeRequest(BaseModel):
    commit_title: str | None = Field(default=None, description="合并 commit 标题")
    commit_message: str | None = Field(default=None, description="合并 commit 消息")
    merge_method: str = Field(default="merge", description="合并方式：merge / squash / rebase")


class MergeResponse(BaseModel):
    merged: bool
    message: str
    sha: str | None = None
    html_url: str | None = None
