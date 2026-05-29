import pytest
from pydantic import HttpUrl

from app.services.github_url_parser import GitHubPullRequestUrlError, parse_github_pr_url


def test_parse_valid_github_pr_url() -> None:
    result = parse_github_pr_url("https://github.com/Sxuan-Coder/ReviewMind/pull/12")

    assert result.owner == "Sxuan-Coder"
    assert result.repo == "ReviewMind"
    assert result.pull_number == 12
    assert str(result.html_url) == "https://github.com/Sxuan-Coder/ReviewMind/pull/12"


def test_parse_url_with_extra_spaces() -> None:
    result = parse_github_pr_url("  https://github.com/owner/repo/pull/1  ")

    assert result.owner == "owner"
    assert result.repo == "repo"
    assert result.pull_number == 1


@pytest.mark.parametrize(
    "pr_url",
    [
        "http://github.com/owner/repo/pull/1",
        "https://gitlab.com/owner/repo/pull/1",
        "https://github.com/owner/repo/issues/1",
        "https://github.com/owner/repo/pull/not-number",
        "https://github.com/owner/repo/pull/0",
        "https://github.com/owner/repo",
        "https://github.com/owner/repo/pull/1/files",
    ],
)
def test_reject_invalid_github_pr_url(pr_url: str) -> None:
    with pytest.raises(GitHubPullRequestUrlError):
        parse_github_pr_url(pr_url)


def test_result_uses_http_url_type() -> None:
    result = parse_github_pr_url("https://github.com/owner/repo/pull/99")

    assert isinstance(result.html_url, HttpUrl)