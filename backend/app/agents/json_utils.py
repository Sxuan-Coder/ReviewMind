"""Agent 共享 JSON 解析工具：从 LLM 返回的原始文本中提取 JSON。"""

import json


def try_parse_json(raw: str, *, fallback_key: str = "findings") -> dict:
    """尝试从 LLM 返回文本中解析 JSON，兼容 markdown code block 包裹。"""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        if "```json" in raw:
            try:
                start = raw.index("```json") + 7
                end = raw.index("```", start)
                return json.loads(raw[start:end].strip())
            except (ValueError, json.JSONDecodeError):
                pass
        if "```" in raw:
            try:
                start = raw.index("```") + 3
                end = raw.index("```", start)
                return json.loads(raw[start:end].strip())
            except (ValueError, json.JSONDecodeError):
                pass
        return {fallback_key: []}