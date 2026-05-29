from urllib.parse import urlparse

from app.schemas.github import GitHubPullRequestRef


class GitHubPullRequestUrlError(ValueError):
    pass


def parse_github_pr_url(pr_url: str) -> GitHubPullRequestRef:
    parsed_url = urlparse(str(pr_url).strip())
    path_parts = [part for part in parsed_url.path.split("/") if part]

    if parsed_url.scheme != "https" or parsed_url.netloc.lower() != "github.com":
        raise GitHubPullRequestUrlError("Invalid GitHub PR URL")

    if len(path_parts) != 4 or path_parts[2] != "pull":
        raise GitHubPullRequestUrlError("GitHub PR URL must match /{owner}/{repo}/pull/{number}")

    owner, repo, _, pull_number_text = path_parts
    if not owner or not repo:
        raise GitHubPullRequestUrlError("GitHub PR URL must include owner and repo")

    if not pull_number_text.isdigit():
        raise GitHubPullRequestUrlError("GitHub PR number must be a positive integer")

    pull_number = int(pull_number_text)
    if pull_number <= 0:
        raise GitHubPullRequestUrlError("GitHub PR number must be a positive integer")

    html_url = f"https://github.com/{owner}/{repo}/pull/{pull_number}"
    return GitHubPullRequestRef(
        owner=owner,
        repo=repo,
        pull_number=pull_number,
        html_url=html_url,
    )