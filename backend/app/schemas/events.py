from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ReviewEventType(StrEnum):
    progress = "progress"
    finding = "finding"
    warning = "warning"
    done = "done"


class ReviewStreamEvent(BaseModel):
    type: ReviewEventType = ReviewEventType.progress
    job_id: str
    step: str
    percent: int = Field(ge=0, le=100)
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)