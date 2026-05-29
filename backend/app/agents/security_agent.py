from uuid import uuid4

from app.schemas.agents import AgentContext, AgentFindingsResult
from app.schemas.review import ReviewFinding


def run(context: AgentContext) -> AgentFindingsResult:
    findings = []
    for diff in context.parsed_diff:
        file = diff.get("file", "unknown")
        changed_lines = diff.get("changed_lines", [])
        if changed_lines:
            findings.append(
                ReviewFinding(
                    id=f"finding_{uuid4().hex[:8]}",
                    agent="security_agent",
                    file=file,
                    line=changed_lines[0],
                    level="INFO",
                    type="security_check",
                    confidence=0.8,
                    description=f"Security scan placeholder for {file}",
                    suggestion="Real security rules will be implemented in later PRs.",
                )
            )
    return AgentFindingsResult(
        agent="security_agent",
        findings=findings,
        summary="Mock security agent completed.",
    )