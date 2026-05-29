from app.schemas.agents import AggregatedRisk, ReviewReportOutput
from app.schemas.review import ReviewFinding, ReviewJobStatus


def generate_report(
    job_id: str,
    risk: AggregatedRisk,
    summary_text: str,
) -> ReviewReportOutput:
    findings = risk.findings
    risk_level = risk.risk_level

    comment_lines = ["## AI Review Summary", ""]
    comment_lines.append(summary_text)
    comment_lines.append("")
    comment_lines.append(f"**Risk Level:** {risk_level}")
    comment_lines.append(f"**Total Findings:** {len(findings)}")
    comment_lines.append("")

    if findings:
        comment_lines.append("### Key Findings")
        for finding in findings[:5]:
            comment_lines.append(f"- [{finding.level}] {finding.description}")
        if len(findings) > 5:
            comment_lines.append(f"- ... and {len(findings) - 5} more")
    else:
        comment_lines.append("No significant findings detected.")

    return ReviewReportOutput(
        summary=summary_text,
        risk_level=risk_level,
        findings=findings,
        review_comment="\n".join(comment_lines),
        stats={
            "total_findings": len(findings),
            "risk_level": risk_level,
            "dedup_count": risk.dedup_count,
        },
    )