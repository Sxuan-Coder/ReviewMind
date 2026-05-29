from uuid import uuid4

from app.schemas.agents import AgentContext, AgentFindingsResult
from app.schemas.review import ReviewFinding


def run(context: AgentContext) -> AgentFindingsResult:
    findings = []
    for diff in context.parsed_diff:
        file = diff.get("file", "unknown")
        if file.startswith("test") or "test" in file.lower():
            findings.append(
                ReviewFinding(
                    id=f"test_{uuid4().hex[:8]}",
                    agent="test_agent",
                    file=file,
                    line=1,
                    level="INFO",
                    type="test_file_changed",
                    confidence=0.9,
                    description=f"Test file modified: {file}",
                    suggestion="Ensure test coverage is maintained.",
                )
            )
    return AgentFindingsResult(
        agent="test_agent",
        findings=findings,
        summary="Mock test agent completed.",
    )
