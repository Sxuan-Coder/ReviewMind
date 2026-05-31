"""Agent prompts：各 agent 的系统提示和用户提示模板。"""

from app.schemas.agents import AgentContext

SUMMARY_SYSTEM = """你是一个代码审查摘要 Agent。请分析给定的 PR diff，生成一份完整的变更摘要。
摘要应包含：
1. PR 整体目标概述（1-2 句）
2. 主要变更点（按文件/模块逐一列出，说明每个变更的作用）
3. 潜在影响范围分析（哪些模块或功能可能受影响）
4. 整体代码质量评价（代码风格、架构合理性、可维护性）

返回 JSON，包含键：summary（字符串，使用 Markdown 格式组织，包含上述四部分）。
重要：summary 字段必须使用简体中文输出，字数不少于 150 字。"""

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

    # 注入框架安全上下文（如果有）
    if context.tech_stack_prompt:
        parts.append(context.tech_stack_prompt)

    if context.pr_info:
        parts.append(f"PR: {context.pr_info.get('title', 'N/A')}")
        parts.append(f"Author: {context.pr_info.get('author', 'N/A')}")
        parts.append("")

    parts.append("Changed files:")
    total_chars = 0
    max_total_chars = 16000  # 总 prompt 截断上限，留给 LLM 足够余量
    for diff in context.parsed_diff:
        file = diff.get("file", "unknown")
        additions = diff.get("additions", 0)
        deletions = diff.get("deletions", 0)
        line = f"  {file} (+{additions}/-{deletions})"
        parts.append(line)
        total_chars += len(line)
        patch = diff.get("patch", "")
        if patch:
            # 单文件 patch 上限提升到 8000 字符
            if len(patch) > 8000:
                patch = patch[:8000] + "\n... (truncated)"
            parts.append(f"  Patch:\n{patch}")
            total_chars += len(patch)
        parts.append("")
        if total_chars > max_total_chars:
            parts.append(f"... 共 {len(context.parsed_diff)} 个文件，已截断过多内容")
            break

    if context.ast_contexts:
        parts.append("AST Context:")
        for ctx in context.ast_contexts[:10]:
            parts.append(f"  {ctx.get('file', '')}:{ctx.get('symbol', 'N/A')} [{ctx.get('start_line')}-{ctx.get('end_line')}]")
        parts.append("")

    if context.rag_contexts:
        parts.append("Related Code (from project knowledge base - use for architectural reference):")
        for ctx in context.rag_contexts[:5]:
            file_path = ctx.get("file_path", "")
            symbol = ctx.get("symbol", "N/A")
            similarity = ctx.get("similarity", 0)
            code = ctx.get("code", "")
            if len(code) > 2000:
                code = code[:2000] + "\n... (truncated)"
            parts.append(f"  File: {file_path} | Symbol: {symbol} | Similarity: {similarity:.2f}")
            parts.append(f"  Code:\n{code}")
        parts.append("")

    return "\n".join(parts)
