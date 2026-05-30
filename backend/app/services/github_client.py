from typing import Any

import httpx

from app.core.cache import redis_cache
from app.core.config import settings
from app.schemas.github import (
    GitHubBranchRef,
    GitHubPullRequestFile,
    GitHubPullRequestInfo,
    GitHubPullRequestRef,
)

# 缓存 TTL（秒）
_CACHE_TTL_PR_INFO = 300       # 5 分钟
_CACHE_TTL_PR_FILES = 300      # 5 分钟


class GitHubClientError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GitHubClient:
    def __init__(
        self,
        api_base_url: str = settings.github_api_base_url,
        token: str | None = settings.github_token,
        timeout_seconds: float = settings.github_timeout_seconds,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds
        self.client = client

    async def fetch_pull_request(self, pr_ref: GitHubPullRequestRef) -> GitHubPullRequestInfo:
        cache_key = f"github:pr:{pr_ref.owner}/{pr_ref.repo}/{pr_ref.pull_number}"
        cached = await redis_cache.get(cache_key)
        if cached is not None:
            return GitHubPullRequestInfo.model_validate(cached)

        payload = await self._get_json(f"/repos/{pr_ref.owner}/{pr_ref.repo}/pulls/{pr_ref.pull_number}")
        info = GitHubPullRequestInfo(
            owner=pr_ref.owner,
            repo=pr_ref.repo,
            pull_number=pr_ref.pull_number,
            title=str(payload.get("title", "")),
            author=str(payload.get("user", {}).get("login", "unknown")),
            state=str(payload.get("state", "unknown")),
            base=_parse_branch_ref(payload.get("base", {})),
            head=_parse_branch_ref(payload.get("head", {})),
            changed_files=int(payload.get("changed_files", 0)),
            additions=int(payload.get("additions", 0)),
            deletions=int(payload.get("deletions", 0)),
            html_url=str(payload.get("html_url", pr_ref.html_url)),
        )
        await redis_cache.set(cache_key, info.model_dump(mode="json"), ttl_seconds=_CACHE_TTL_PR_INFO)
        return info

    async def fetch_pull_request_files(self, pr_ref: GitHubPullRequestRef) -> list[GitHubPullRequestFile]:
        cache_key = f"github:files:{pr_ref.owner}/{pr_ref.repo}/{pr_ref.pull_number}"
        cached = await redis_cache.get(cache_key)
        if cached is not None and isinstance(cached, list):
            return [GitHubPullRequestFile.model_validate(item) for item in cached]

        payload = await self._get_json(f"/repos/{pr_ref.owner}/{pr_ref.repo}/pulls/{pr_ref.pull_number}/files")
        if not isinstance(payload, list):
            raise GitHubClientError("GitHub files response is invalid")

        files = [
            GitHubPullRequestFile(
                filename=str(item.get("filename", "")),
                status=str(item.get("status", "modified")),
                additions=int(item.get("additions", 0)),
                deletions=int(item.get("deletions", 0)),
                patch=item.get("patch"),
            )
            for item in payload
        ]
        await redis_cache.set(cache_key, [f.model_dump(mode="json") for f in files], ttl_seconds=_CACHE_TTL_PR_FILES)
        return files

    async def _get_json(self, path: str) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        if self.client is not None:
            response = await self.client.get(path, headers=headers)
            return _handle_response(response)

        async with httpx.AsyncClient(base_url=self.api_base_url, timeout=self.timeout_seconds) as client:
            response = await client.get(path, headers=headers)
            return _handle_response(response)


def _handle_response(response: httpx.Response) -> Any:
    if response.status_code == 401:
        raise GitHubClientError("GitHub token is invalid", status_code=401)
    if response.status_code == 403:
        raise GitHubClientError("GitHub API rate limit or permission denied", status_code=403)
    if response.status_code == 404:
        raise GitHubClientError("GitHub pull request was not found", status_code=404)
    if response.status_code >= 400:
        raise GitHubClientError("GitHub API request failed", status_code=response.status_code)
    return response.json()


def _parse_branch_ref(payload: dict[str, Any]) -> GitHubBranchRef:
    return GitHubBranchRef(
        ref=str(payload.get("ref", "")),
        sha=str(payload.get("sha", "")),
    )