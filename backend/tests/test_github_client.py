import httpx
import pytest

from app.schemas.github import GitHubPullRequestRef
from app.services.github_client import GitHubClient, GitHubClientError


@pytest.mark.anyio
async def test_fetch_pull_request_info() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/owner/repo/pulls/12"
        return httpx.Response(
            200,
            json={
                "title": "Add review engine",
                "user": {"login": "alice"},
                "state": "open",
                "base": {"ref": "main", "sha": "base-sha"},
                "head": {"ref": "feature", "sha": "head-sha"},
                "changed_files": 2,
                "additions": 10,
                "deletions": 3,
                "html_url": "https://github.com/owner/repo/pull/12",
            },
        )

    client = GitHubClient(client=httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.com"))
    result = await client.fetch_pull_request(make_ref())

    assert result.title == "Add review engine"
    assert result.author == "alice"
    assert result.base.ref == "main"
    assert result.head.sha == "head-sha"
    assert result.changed_files == 2


@pytest.mark.anyio
async def test_fetch_pull_request_files() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "filename": "backend/app/main.py",
                    "status": "modified",
                    "additions": 4,
                    "deletions": 1,
                    "patch": "@@ -1 +1 @@",
                }
            ],
        )

    client = GitHubClient(client=httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.com"))
    result = await client.fetch_pull_request_files(make_ref())

    assert len(result) == 1
    assert result[0].filename == "backend/app/main.py"
    assert result[0].patch == "@@ -1 +1 @@"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status_code", "expected_message"),
    [
        (401, "GitHub token is invalid"),
        (403, "GitHub API rate limit or permission denied"),
        (404, "GitHub pull request was not found"),
    ],
)
async def test_github_error_mapping(status_code: int, expected_message: str) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"message": "error"})

    client = GitHubClient(client=httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.com"))

    with pytest.raises(GitHubClientError) as error:
        await client.fetch_pull_request(make_ref())

    assert str(error.value) == expected_message
    assert error.value.status_code == status_code


@pytest.mark.anyio
async def test_authorization_header_is_added_without_leaking_token() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret-token"
        return httpx.Response(
            200,
            json={
                "title": "Safe token",
                "user": {"login": "alice"},
                "state": "open",
                "base": {"ref": "main", "sha": "base-sha"},
                "head": {"ref": "feature", "sha": "head-sha"},
                "changed_files": 0,
                "additions": 0,
                "deletions": 0,
                "html_url": "https://github.com/owner/repo/pull/12",
            },
        )

    client = GitHubClient(
        token="secret-token",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.com"),
    )
    result = await client.fetch_pull_request(make_ref())

    assert result.title == "Safe token"


def make_ref() -> GitHubPullRequestRef:
    return GitHubPullRequestRef(
        owner="owner",
        repo="repo",
        pull_number=12,
        html_url="https://github.com/owner/repo/pull/12",
    )