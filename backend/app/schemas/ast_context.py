from pydantic import BaseModel, Field


class AstContext(BaseModel):
    file: str
    symbol: str | None = None
    start_line: int
    end_line: int
    changed_lines: list[int] = Field(default_factory=list)
    language: str
    code: str
    degraded: bool = False
    reason: str | None = None