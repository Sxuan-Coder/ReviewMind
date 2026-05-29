from pydantic import BaseModel, Field


class PullRequestFile(BaseModel):
    filename: str
    status: str = "modified"
    additions: int = 0
    deletions: int = 0
    patch: str | None = None


class DiffLine(BaseModel):
    old_line_number: int | None = None
    new_line_number: int | None = None
    content: str
    change_type: str


class DiffHunk(BaseModel):
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[DiffLine] = Field(default_factory=list)


class ParsedDiffFile(BaseModel):
    file: str
    status: str
    additions: int = 0
    deletions: int = 0
    changed_lines: list[int] = Field(default_factory=list)
    deleted_lines: list[int] = Field(default_factory=list)
    hunks: list[DiffHunk] = Field(default_factory=list)