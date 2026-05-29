from app.schemas.agents import AgentContext, AgentFindingsResult
from app.schemas.review import ReviewFinding


def run(context: AgentContext) -> AgentFindingsResult:
    files = [diff.get("file", "unknown") for diff in context.parsed_diff]
    return AgentFindingsResult(
        agent="summary_agent",
        summary=f"PR 涉及 {len(files)} 个文件变更，正在进行基础 Diff 分析。",
        findings=[],
    )