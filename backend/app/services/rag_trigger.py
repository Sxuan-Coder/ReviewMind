"""RAG 分级触发评估器。

根据变更规模、文件类型、风险关键词自动决定 RAG 检索级别：
- NONE: 跳过 RAG，节省 embedding 调用
- LIGHT: 轻量 RAG，仅对风险文件检索
- FULL: 完整 RAG，对所有变更文件检索
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class RagTriggerLevel(Enum):
    NONE = 0   # 跳过 RAG
    LIGHT = 1  # 轻量 RAG：仅风险文件
    FULL = 2   # 完整 RAG：所有变更文件


# 风险关键词（出现在 PR 标题/描述中表示高风险）
RISK_KEYWORDS: set[str] = {
    "auth", "security", "crypto", "encrypt", "decrypt", "password",
    "token", "secret", "key", "certificate", "ssl", "tls", "oauth",
    "permission", "admin", "role", "access", "payment", "billing",
    "transaction", "sql", "injection", "xss", "csrf", "sanitize",
    "validate", "critical", "urgent", "hotfix", "vulnerability",
    "race condition", "deadlock", "concurrent",
}

# 风险文件模式（路径包含这些关键词表示高风险）
RISK_FILE_PATTERNS: set[str] = {
    "auth", "security", "crypto", "encrypt", "password", "token",
    "admin", "permission", "payment", "billing", "database", "migration",
    "config", "secret", "key", "certificate", "middleware", "guard",
    "sanitize", "validate",
}


def _count_risk_keyword_matches(text: str) -> int:
    """统计文本中风险关键词命中次数。"""
    if not text:
        return 0
    text_lower = text.lower()
    return sum(1 for kw in RISK_KEYWORDS if kw in text_lower)


def _count_risk_file_matches(file_paths: list[str]) -> int:
    """统计文件路径中风险模式命中次数。"""
    count = 0
    for path in file_paths:
        lower = path.lower()
        for pattern in RISK_FILE_PATTERNS:
            if pattern in lower:
                count += 1
                break  # 每个文件只计一次
    return count


def evaluate_rag_trigger(
    pr_info: dict[str, Any] | None,
    filtered_files: dict[str, Any] | None,
    parsed_diff: list[dict[str, Any]] | None,
    *,
    enable_rag: bool = True,
) -> tuple[RagTriggerLevel, str]:
    """评估 RAG 触发级别并返回原因。

    返回 (RagTriggerLevel, reason)。
    """
    if not enable_rag:
        return RagTriggerLevel.NONE, "RAG disabled by config"

    if not parsed_diff:
        return RagTriggerLevel.NONE, "No diff data available"

    # 收集变更信息
    file_paths: list[str] = []
    total_lines = 0

    for diff in parsed_diff:
        file = diff.get("file", "")
        if file:
            file_paths.append(file)
        total_lines += diff.get("additions", 0) + diff.get("deletions", 0)

    num_files = len(file_paths)

    # 收集 PR 文本用于关键词检测
    pr_text = ""
    if pr_info:
        pr_text = f"{pr_info.get('title', '')} {pr_info.get('body', '')}"

    # 信号计算
    keyword_matches = _count_risk_keyword_matches(pr_text)
    risk_file_matches = _count_risk_file_matches(file_paths)

    # 分级决策
    score = 0
    reasons: list[str] = []

    # 文件数信号
    if num_files >= settings.rag_full_min_files:
        score += 4
        reasons.append(f"file count {num_files} >= {settings.rag_full_min_files}")
    elif num_files >= settings.rag_light_min_files:
        score += 2
        reasons.append(f"file count {num_files} >= {settings.rag_light_min_files}")

    # 行数信号
    if total_lines >= settings.rag_full_min_lines:
        score += 4
        reasons.append(f"lines {total_lines} >= {settings.rag_full_min_lines}")
    elif total_lines >= settings.rag_light_min_lines:
        score += 2
        reasons.append(f"lines {total_lines} >= {settings.rag_light_min_lines}")

    # 风险关键词信号
    if keyword_matches >= 3:
        score += 4
        reasons.append(f"risk keywords {keyword_matches} >= 3")
    elif keyword_matches >= 1:
        score += 2
        reasons.append(f"risk keywords {keyword_matches} >= 1")

    # 风险文件信号
    if risk_file_matches >= 3:
        score += 4
        reasons.append(f"risk files {risk_file_matches} >= 3")
    elif risk_file_matches >= 1:
        score += 2
        reasons.append(f"risk files {risk_file_matches} >= 1")

    # 根据总分决定级别
    if score >= 8:
        level = RagTriggerLevel.FULL
    elif score >= 3:
        level = RagTriggerLevel.LIGHT
    else:
        level = RagTriggerLevel.NONE

    reason = "; ".join(reasons) if reasons else "No risk signal triggered"
    logger.info(
        "[RAG_TRIGGER] level=%s score=%d files=%d lines=%d kw=%d risk_files=%d | %s",
        level.name, score, num_files, total_lines, keyword_matches, risk_file_matches, reason,
    )
    return level, reason


def get_risk_file_paths(file_paths: list[str]) -> list[str]:
    """从文件路径列表中筛选出匹配风险模式的文件。"""
    return [
        path for path in file_paths
        if any(pattern in path.lower() for pattern in RISK_FILE_PATTERNS)
    ]
