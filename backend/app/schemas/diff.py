from pydantic import BaseModel, Field


class PullRequestFile(BaseModel):
    filename: str
    status: str = "modified"
    additions: int = 0
    deletions: int = 0
    patch: str | None = None


class ExcludedDiffFile(BaseModel):
    file: PullRequestFile
    exclude_reason: str


class DiffFilterResult(BaseModel):
    included_files: list[PullRequestFile] = Field(default_factory=list)
    excluded_files: list[ExcludedDiffFile] = Field(default_factory=list)
    total_additions: int = 0
    total_deletions: int = 0