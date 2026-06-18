import hashlib
import hmac
import json
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.schemas.review import CreateReviewJobRequest, CreateReviewJobResponse, ReviewJobStatus
from app.services.github_webhook import GitHubWebhookResult
from app.services.github_webhook import (
    GitHubWebhookError,
    handle_github_webhook,
    parse_issue_comment_command,
    verify_github_signature,
)


SECRET = "webhook-secret"


@pytest.fixture(autouse=True)
def _webhook_settings(monkeypatch):
    monkeypatch.setattr(settings, "github_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "github_review_trigger", "@reviewmind review")
    monkeypatch.setattr(settings, "github_bot_login", "reviewmind")
    monkeypatch.setattr(settings, "github_allowed_repos", [])
    monkeypatch.setattr(settings, "github_token", "test-token")
    yield


def test_verify_github_signature_accepts_valid_signature() -> None:
    raw = b'{"ok":true}'
    verify_github_signature(raw_body=raw, signature=_signature(raw))


def test_verify_github_signature_rejects_invalid_signature() -> None:
    with pytest.raises(GitHubWebhookError) as exc:
        verify_github_signature(raw_body=b"{}", signature="sha256=bad")

    assert exc.value.status_code == 401
    assert str(exc.value) == "Invalid GitHub webhook signature"


def test_parse_issue_comment_command_extracts_pull_request() -> None:
    command = parse_issue_comment_command(_payload(body="@ReviewMind review please"))

    assert command is not None
    assert command.owner == "owner"
    assert command.repo == "repo"
    assert command.pull_number == 12
    assert command.pr_url == "https://github.com/owner/repo/pull/12"
    assert command.commenter == "alice"


def test_parse_issue_comment_command_ignores_non_triggers() -> None:
    payloads = [
        _payload(action="edited"),
        _payload(body="looks good"),
        _payload(is_pull_request=False),
        _payload(commenter="reviewmind"),
        _payload(commenter="github-actions[bot]", user_type="Bot"),
    ]

    for payload in payloads:
        assert parse_issue_comment_command(payload) is None


def test_parse_issue_comment_command_respects_allowed_repos(monkeypatch) -> None:
    monkeypatch.setattr(settings, "github_allowed_repos", ["other/repo"])

    assert parse_issue_comment_command(_payload()) is None


@pytest.mark.anyio
async def test_handle_github_webhook_creates_job_and_start_comment(monkeypatch) -> None:
    raw = _raw_payload(_payload())
    service = FakeReviewJobService()
    posted_comments: list[dict] = []

    async def fake_post_pr_comment(**kwargs):
        posted_comments.append(kwargs)
        return FakeCommentResult(html_url="https://github.com/owner/repo/pull/12#issuecomment-1")

    async def noop_final_comment(*_args, **_kwargs):
        return None

    async def fake_duplicate(_delivery_id: str) -> bool:
        return False

    monkeypatch.setattr("app.services.github_webhook.post_pr_comment", fake_post_pr_comment)
    monkeypatch.setattr("app.services.github_webhook._post_final_comment_when_done", noop_final_comment)
    monkeypatch.setattr("app.services.github_webhook._is_duplicate_delivery", fake_duplicate)

    result = await handle_github_webhook(
        event="issue_comment",
        delivery_id="delivery-1",
        signature=_signature(raw),
        raw_body=raw,
        service=service,
    )

    assert result.accepted is True
    assert result.ignored is False
    assert result.job_id == "rev_webhook"
    assert result.pr_url == "https://github.com/owner/repo/pull/12"
    assert service.requests[0].pr_url.unicode_string() == "https://github.com/owner/repo/pull/12"
    assert service.requests[0].github_token == "test-token"
    assert posted_comments[0]["owner"] == "owner"
    assert posted_comments[0]["repo"] == "repo"
    assert posted_comments[0]["pull_number"] == 12
    assert "ReviewMind 已开始审查" in posted_comments[0]["body"]


@pytest.mark.anyio
async def test_handle_github_webhook_ignores_unsupported_event(monkeypatch) -> None:
    raw = _raw_payload(_payload())
    monkeypatch.setattr("app.services.github_webhook._is_duplicate_delivery", _not_duplicate)

    result = await handle_github_webhook(
        event="pull_request",
        delivery_id="delivery-2",
        signature=_signature(raw),
        raw_body=raw,
        service=FakeReviewJobService(),
    )

    assert result.ignored is True
    assert result.reason == "unsupported_event"


@pytest.mark.anyio
async def test_handle_github_webhook_ignores_duplicate_delivery(monkeypatch) -> None:
    raw = _raw_payload(_payload())

    async def duplicate(_delivery_id: str) -> bool:
        return True

    monkeypatch.setattr("app.services.github_webhook._is_duplicate_delivery", duplicate)

    result = await handle_github_webhook(
        event="issue_comment",
        delivery_id="delivery-3",
        signature=_signature(raw),
        raw_body=raw,
        service=FakeReviewJobService(),
    )

    assert result.ignored is True
    assert result.reason == "duplicate_delivery"


def test_webhook_route_returns_structured_response(monkeypatch) -> None:
    async def fake_handle_github_webhook(**_kwargs):
        return GitHubWebhookResult(
            accepted=True,
            ignored=False,
            reason="review_job_created",
            job_id="rev_route",
            pr_url="https://github.com/owner/repo/pull/12",
            start_comment_url="https://github.com/owner/repo/pull/12#issuecomment-1",
        )

    monkeypatch.setattr("app.api.github_webhook.handle_github_webhook", fake_handle_github_webhook)

    response = TestClient(app).post(
        "/api/v1/github/webhook",
        content=_raw_payload(_payload()),
        headers={
            "X-GitHub-Event": "issue_comment",
            "X-GitHub-Delivery": "delivery-route",
            "X-Hub-Signature-256": "sha256=test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 20200
    assert body["data"]["accepted"] is True
    assert body["data"]["job_id"] == "rev_route"


async def _not_duplicate(_delivery_id: str) -> bool:
    return False


@dataclass
class FakeCommentResult:
    html_url: str
    comment_id: int = 1


class FakeReviewJobService:
    def __init__(self) -> None:
        self.requests: list[CreateReviewJobRequest] = []

    async def create_job(self, request: CreateReviewJobRequest) -> CreateReviewJobResponse:
        self.requests.append(request)
        return CreateReviewJobResponse(
            job_id="rev_webhook",
            status=ReviewJobStatus.pending,
            stream_url="/api/v1/review/stream/rev_webhook",
            report_url="/api/v1/review/jobs/rev_webhook",
        )


def _payload(
    *,
    action: str = "created",
    body: str = "@reviewmind review",
    commenter: str = "alice",
    user_type: str = "User",
    is_pull_request: bool = True,
) -> dict:
    issue = {
        "number": 12,
        "html_url": "https://github.com/owner/repo/pull/12",
    }
    if is_pull_request:
        issue["pull_request"] = {"url": "https://api.github.com/repos/owner/repo/pulls/12"}

    return {
        "action": action,
        "issue": issue,
        "comment": {
            "body": body,
            "user": {
                "login": commenter,
                "type": user_type,
            },
        },
        "repository": {
            "name": "repo",
            "owner": {
                "login": "owner",
            },
        },
    }


def _raw_payload(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _signature(raw: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
