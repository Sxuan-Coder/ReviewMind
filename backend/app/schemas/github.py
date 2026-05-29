from pydantic import BaseModel, Field, HttpUrl


class GitHubPullRequestRef(BaseModel):
    owner: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    pull_number: int = Field(gt=0)
    html_url: HttpUrl