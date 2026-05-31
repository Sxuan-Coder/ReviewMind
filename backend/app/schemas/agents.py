from typing import Any

from pydantic import BaseModel, Field

from app.schemas.review import ReviewFinding


class AgentContext(BaseModel):
    pr_info: dict[str, Any] = Field(default_factory=dict)
    parsed_diff: list[dict[str, Any]] = Field(default_factory=list)
    ast_contexts: list[dict[str, Any]] = Field(default_factory=list)
    rag_contexts: list[dict[str, Any]] = Field(default_factory=list)


class AgentFindingsResult(BaseModel):
    agent: str
    findings: list[ReviewFinding] = Field(default_factory=list)
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)


class RiskLevel(str):
    pass


RISK_CRITICAL = "CRITICAL"
RISK_HIGH = "HIGH"
RISK_MEDIUM = "MEDIUM"
RISK_LOW = "LOW"
RISK_NONE = "NONE"

RISK_ORDER: dict[str, int] = {
    RISK_CRITICAL: 4,
    RISK_HIGH: 3,
    RISK_MEDIUM: 2,
    RISK_LOW: 1,
    RISK_NONE: 0,
}


class AggregatedRisk(BaseModel):
    risk_level: str
    findings: list[ReviewFinding] = Field(default_factory=list)
    summary: str = ""
    dedup_count: int = 0


class ReviewReportOutput(BaseModel):
    summary: str
    risk_level: str
    findings: list[ReviewFinding] = Field(default_factory=list)
    review_comment: str
    stats: dict[str, Any] = Field(default_factory=dict)