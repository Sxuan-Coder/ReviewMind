from app.schemas.agents import (
    AgentFindingsResult,
    AggregatedRisk,
    RISK_ORDER,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_CRITICAL,
)
from app.schemas.review import ReviewFinding


def aggregate(agent_results: list[AgentFindingsResult]) -> AggregatedRisk:
    all_findings: list[ReviewFinding] = []
    for result in agent_results:
        all_findings.extend(result.findings)

    deduped = _dedupe_findings(all_findings)
    risk_level = _calculate_risk_level(deduped)

    return AggregatedRisk(
        risk_level=risk_level,
        findings=deduped,
        summary=f"Aggregated {len(deduped)} findings from {len(agent_results)} agents.",
        dedup_count=len(all_findings) - len(deduped),
    )


def _dedupe_findings(findings: list[ReviewFinding]) -> list[ReviewFinding]:
    seen: set[tuple[str, str, int, str]] = set()
    unique: list[ReviewFinding] = []
    for f in findings:
        key = (f.agent, f.file, f.line, f.type)
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def _calculate_risk_level(findings: list[ReviewFinding]) -> str:
    if not findings:
        return RISK_LOW

    has_critical = any(f.level == "CRITICAL" for f in findings)
    has_high = any(f.level == "HIGH" for f in findings)
    has_medium = any(f.level in ("MEDIUM", "WARNING") for f in findings)

    if has_critical:
        return RISK_CRITICAL
    if has_high:
        return RISK_HIGH
    if has_medium:
        return RISK_MEDIUM
    return RISK_LOW