from uuid import uuid4

from app.schemas.agents import AgentContext, AgentFindingsResult
from app.schemas.review import ReviewFinding


def run(context: AgentContext) -> AgentFindingsResult:
    findings = []
    for diff in context.parsed_diff:
        file = diff.get("file", "unknown")
        additions = diff.get("additions", 0)
        if additions > 50:
            findings.append(
                ReviewFinding(
                    id=f"perf_{uuid4().hex[:8]}",
                    agent="performance_agent",
                    file=file,
                    line=1,
                    level="WARNING",
                    type="large_change",
                    confidence=0.7,
                    description=f"Large change detected: {additions} lines added to {file}",
                    suggestion="Consider breaking large changes into smaller PRs for better review.",
                )
            )
    return AgentFindingsResult(
        agent="performance_agent",
        findings=findings,
        summary="Mock performance agent completed.",
    )
