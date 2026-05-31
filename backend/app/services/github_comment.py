"""GitHub PR 评论服务：调用 GitHub Issues Comments API 发布 Review 评论。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class GitHubCommentError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class GitHubCommentResult:
    comment_id: int
    html_url: str


async def post_pr_comment(
    owner: str,
    repo: str,
    pull_number: int,
    body: str,
    github_token: str | None = None,
) -> GitHubCommentResult:
    """在指定 PR 上发布评论。

    调用 POST /repos/{owner}/{repo}/issues/{number}/comments。
    需要 GITHUB_TOKEN 具备 repo 权限。
    """
    token = github_token or settings.github_token
    if not token:
        raise GitHubCommentError("GITHUB_TOKEN is not configured")

    url = f"{settings.github_api_base_url}/repos/{owner}/{repo}/issues/{pull_number}/comments"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }
    payload = {"body": body}

    async with httpx.AsyncClient(timeout=settings.github_timeout_seconds) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code == 401:
        raise GitHubCommentError("GitHub token is invalid", status_code=401)
    if response.status_code == 403:
        raise GitHubCommentError("GitHub API rate limit or permission denied", status_code=403)
    if response.status_code == 404:
        raise GitHubCommentError("GitHub pull request was not found", status_code=404)
    if response.status_code >= 400:
        raise GitHubCommentError(
            f"GitHub comment API failed: {response.status_code}", status_code=response.status_code
        )

    data = response.json()
    return GitHubCommentResult(
        comment_id=int(data.get("id", 0)),
        html_url=str(data.get("html_url", "")),
    )