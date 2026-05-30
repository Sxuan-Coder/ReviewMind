"""Agent prompts：各 agent 的系统提示和用户提示模板。"""

from app.schemas.agents import AgentContext

SUMMARY_SYSTEM = """你是一个代码审查摘要 Agent。请分析给定的 PR diff，生成一段简洁的变更摘要。
返回 JSON，包含键：summary（字符串）。
重要：summary 字段必须使用简体中文输出。"""

SECURITY_SYSTEM = """你是一个专注安全的代码审查 Agent。请分析给定的 PR diff 是否存在安全问题。
重点关注：SQL 注入、XSS、硬编码密钥、不安全的加密、路径穿越、命令注入、SSRF、不安全的反序列化。
返回 JSON，包含键 "findings"，每个 finding 含字段：id, agent, file, line, level (CRITICAL/HIGH/MEDIUM/LOW/INFO), type, confidence (0-1), description, suggestion。
重要：保持上述 JSON 键名与 level 枚举值（英文）不变；description 与 suggestion 字段必须使用简体中文输出。"""

PERFORMANCE_SYSTEM = """你是一个专注性能的代码审查 Agent。请分析给定的 PR diff 是否存在性能问题。
重点关注：N+1 查询、缺失索引、内存泄漏、不必要的内存分配、阻塞式 I/O、缺失缓存、过大的负载。
返回 JSON，包含键 "findings"，每个 finding 含字段：id, agent, file, line, level (CRITICAL/HIGH/MEDIUM/LOW/INFO), type, confidence (0-1), description, suggestion。
重要：保持上述 JSON 键名与 level 枚举值（英文）不变；description 与 suggestion 字段必须使用简体中文输出。"""

TEST_SYSTEM = """你是一个专注测试质量的代码审查 Agent。请分析给定的 PR diff 的测试覆盖与测试质量。
重点关注：缺失测试覆盖、不稳定（flaky）的测试模式、测试隔离问题、缺失的边界用例。
返回 JSON，包含键 "findings"，每个 finding 含字段：id, agent, file, line, level (CRITICAL/HIGH/MEDIUM/LOW/INFO), type, confidence (0-1), description, suggestion。
重要：保持上述 JSON 键名与 level 枚举值（英文）不变；description 与 suggestion 字段必须使用简体中文输出。"""


def build_user_prompt(context: AgentContext) -> str:
    """构建 agent 通用的用户提示。"""
    parts = []

    if context.pr_info:
        parts.append(f"PR: {context.pr_info.get('title', 'N/A')}")
        parts.append(f"Author: {context.pr_info.get('author', 'N/A')}")
        parts.append("")

    parts.append("Changed files:")
    for diff in context.parsed_diff:
        file = diff.get("file", "unknown")
        additions = diff.get("additions", 0)
        deletions = diff.get("deletions", 0)
        parts.append(f"  {file} (+{additions}/-{deletions})")
        patch = diff.get("patch", "")
        if patch:
            # 截断过长的 patch
            if len(patch) > 2000:
                patch = patch[:2000] + "\n... (truncated)"
            parts.append(f"  Patch:\n{patch}")
        parts.append("")

    if context.ast_contexts:
        parts.append("AST Context:")
        for ctx in context.ast_contexts[:10]:
            parts.append(f"  {ctx.get('file', '')}:{ctx.get('symbol', 'N/A')} [{ctx.get('start_line')}-{ctx.get('end_line')}]")
        parts.append("")

    return "\n".join(parts)
