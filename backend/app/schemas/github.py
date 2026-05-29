from pydantic import BaseModel, Field, HttpUrl


class GitHubPullRequestRef(BaseModel):
    owner: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    pull_number: int = Field(gt=0)
    html_url: HttpUrl


class GitHubUser(BaseModel):
    login: str
    html_url: HttpUrl | None = None


class GitHubBranchRef(BaseModel):
    ref: str
    sha: str


class GitHubPullRequestInfo(BaseModel):
    owner: str
    repo: str
    pull_number: int
    title: str
    author: str
    state: str
    base: GitHubBranchRef
    head: GitHubBranchRef
    changed_files: int
    additions: int
    deletions: int
    html_url: HttpUrl


class GitHubPullRequestFile(BaseModel):
    filename: str
    status: str
    additions: int = 0
    deletions: int = 0
    patch: str | None = None