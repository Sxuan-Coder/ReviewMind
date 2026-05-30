from app.schemas.agents import AggregatedRisk, ReviewReportOutput
from app.schemas.review import ReviewFinding, ReviewJobStatus


def generate_report(
    job_id: str,
    risk: AggregatedRisk,
    summary_text: str,
) -> ReviewReportOutput:
    findings = risk.findings
    risk_level = risk.risk_level

    comment_lines = ["## AI 审查摘要", ""]
    comment_lines.append(summary_text)
    comment_lines.append("")
    comment_lines.append(f"**风险等级：** {risk_level}")
    comment_lines.append(f"**风险发现数：** {len(findings)}")
    comment_lines.append("")

    if findings:
        comment_lines.append("### 主要发现")
        for finding in findings[:5]:
            comment_lines.append(f"- [{finding.level}] {finding.description}")
        if len(findings) > 5:
            comment_lines.append(f"- ……还有 {len(findings) - 5} 项")
    else:
        comment_lines.append("未发现明显问题。")

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