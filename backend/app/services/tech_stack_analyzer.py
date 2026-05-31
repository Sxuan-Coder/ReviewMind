"""技术栈分析器：从 changed files 中推断项目框架，输出安全审查上下文。

Security Agent 等审查 Agent 可据此判断哪些威胁类别在本项目中不适用，
从而减少框架自带防御机制导致的误报。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FrameworkProfile:
    """项目技术栈概要，用于注入到 Agent prompt 中。"""

    frontend_framework: str = ""
    backend_framework: str = ""
    orm: str = ""
    validation: str = ""
    template_engine: str = ""
    language: str = ""

    # 安全相关的框架自带防线描述
    security_notes: list[str] = field(default_factory=list)

    def to_prompt_block(self) -> str:
        """生成可注入到 system prompt 的框架上下文文本。"""
        if not self.security_notes:
            return ""
        lines = ["\n## 项目技术栈与安全上下文（请在审查时参考）"]
        for note in self.security_notes:
            lines.append(f"- {note}")
        lines.append("")
        return "\n".join(lines)


# ---- 关键词 → 框架推断规则 ----

_FRAMEWORK_RULES: list[dict[str, Any]] = [
    # 前端
    {
        "match_files": ("package.json",),
        "match_content": (b"react", b'"react"'),
        "profile": {
            "frontend_framework": "React",
            "template_engine": "React JSX (auto-escaping)",
        },
        "notes": [
            "前端使用 React，JSX 渲染自动转义 HTML，无需手动 escape",
            "React 不使用字符串拼接构建 DOM，XSS 风险极低",
        ],
    },
    {
        "match_files": ("package.json",),
        "match_content": (b"vue", b'"vue"'),
        "profile": {
            "frontend_framework": "Vue",
            "template_engine": "Vue template (auto-escaping)",
        },
        "notes": [
            "前端使用 Vue，模板自动转义 HTML",
        ],
    },
    # 后端
    {
        "match_files": ("requirements.txt", "pyproject.toml"),
        "match_content": (b"fastapi",),
        "profile": {
            "backend_framework": "FastAPI",
        },
    },
    {
        "match_files": ("requirements.txt", "pyproject.toml"),
        "match_content": (b"sqlalchemy",),
        "profile": {
            "orm": "SQLAlchemy",
        },
        "notes": [
            "后端使用 SQLAlchemy ORM，不拼接原始 SQL，SQL 注入风险极低",
        ],
    },
    {
        "match_files": ("requirements.txt", "pyproject.toml"),
        "match_content": (b"pydantic",),
        "profile": {
            "validation": "Pydantic",
        },
        "notes": [
            "输入校验使用 Pydantic，自动做类型验证和数据清洗",
        ],
    },
    {
        "match_files": ("requirements.txt", "pyproject.toml"),
        "match_content": (b"django",),
        "profile": {
            "backend_framework": "Django",
            "orm": "Django ORM",
            "template_engine": "Django Templates (auto-escaping)",
        },
        "notes": [
            "后端使用 Django ORM，不拼接原始 SQL",
            "Django 模板默认自动转义 HTML",
        ],
    },
]


def analyze_tech_stack(changed_files: list[dict[str, Any]]) -> FrameworkProfile:
    """从 changed files 列表中推断技术栈。

    扫描每个文件的 filename + patch 内容，匹配预定义规则，
    合并生成 FrameworkProfile。非关键功能，任何异常均降级为空 profile。

    Args:
        changed_files: GitHub PR file 列表，每个含 filename / patch 等字段。

    Returns:
        合并后的 FrameworkProfile。
    """
    profile = FrameworkProfile()
    detected_notes: set[str] = set()

    try:
        for rule in _FRAMEWORK_RULES:
            matched = False
            for f in changed_files:
                filename = f.get("filename", "")
                # 检查文件名是否匹配
                if not any(filename.endswith(pattern) for pattern in rule["match_files"]):
                    continue
                # 检查内容关键词
                patch = f.get("patch", "") or ""
                patch_bytes = patch.encode("utf-8", errors="ignore").lower()
                if any(kw.lower() in patch_bytes for kw in rule["match_content"]):
                    matched = True
                    break
            if matched:
                # 合并 profile 字段
                for key, value in rule.get("profile", {}).items():
                    if value and not getattr(profile, key, None):
                        setattr(profile, key, value)
                # 合并 notes（去重）
                for note in rule.get("notes", []):
                    detected_notes.add(note)
    except Exception:
        pass

    profile.security_notes = sorted(detected_notes)
    return profile