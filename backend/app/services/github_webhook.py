"""GitHub Webhook 触发 Review Job 的服务层。"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from typing import Any

from app.core.cache import redis_cache
from app.core.config import settings
from app.schemas.review import CreateReviewJobRequest, ReviewJobStatus
from app.services.github_comment import GitHubCommentError, post_pr_comment
from app.services.review_job_service import ReviewJobService, review_job_service

logger = logging.getLogger(__name__)

_DELIVERY_CACHE_TTL_SECONDS = 24 * 60 * 60


class GitHubWebhookError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class GitHubWebhookResult:
    accepted: bool
    ignored: bool
    reason: str
    job_id: str | None = None
    pr_url: str | None = None
    start_comment_url: str | None = None


@dataclass(frozen=True)
class PullRequestCommand:
    owner: str
    repo: str
    pull_number: int
    pr_url: str
    commenter: str
    body: str


async def handle_github_webhook(
    *,
    event: str | None,
    delivery_id: str | None,
    signature: str | None,
    raw_body: bytes,
    service: ReviewJobService = review_job_service,
) -> GitHubWebhookResult:
    """处理 GitHub Webhook，并在命中触发词时创建 Review Job。"""
    verify_github_signature(raw_body=raw_body, signature=signature)

    if not delivery_id:
        raise GitHubWebhookError("Missing X-GitHub-Delivery header", status_code=400)
    if await _is_duplicate_delivery(delivery_id):
        return GitHubWebhookResult(accepted=False, ignored=True, reason="duplicate_delivery")

    payload = _decode_payload(raw_body)
    if event != "issue_comment":
        return GitHubWebhookResult(accepted=False, ignored=True, reason="unsupported_event")

    command = parse_issue_comment_command(payload)
    if command is None:
        return GitHubWebhookResult(accepted=False, ignored=True, reason="no_review_trigger")

    request = CreateReviewJobRequest(pr_url=command.pr_url, github_token=settings.github_token)
    response = await service.create_job(request)

    start_comment_url = await _post_start_comment(command, response.job_id)
    asyncio.create_task(_post_final_comment_when_done(command, response.job_id, service))

    return GitHubWebhookResult(
        accepted=True,
        ignored=False,
        reason="review_job_created",
        job_id=response.job_id,
        pr_url=command.pr_url,
        start_comment_url=start_comment_url,
    )


def verify_github_signature(*, raw_body: bytes, signature: str | None) -> None:
    """校验 GitHub Webhook 的 X-Hub-Signature-256。"""
    secret = settings.github_webhook_secret
    if not secret:
        raise GitHubWebhookError("GITHUB_WEBHOOK_SECRET is not configured", status_code=500)
    if not signature:
        raise GitHubWebhookError("Missing X-Hub-Signature-256 header", status_code=401)

    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise GitHubWebhookError("Invalid GitHub webhook signature", status_code=401)


def parse_issue_comment_command(payload: dict[str, Any]) -> PullRequestCommand | None:
    """从 issue_comment payload 中提取 Review 触发命令。"""
    if payload.get("action") != "created":
        return None

    issue = payload.get("issue")
    comment = payload.get("comment")
    repository = payload.get("repository")
    if not isinstance(issue, dict) or not isinstance(comment, dict) or not isinstance(repository, dict):
        return None
    if "pull_request" not in issue:
        return None

    body = str(comment.get("body", ""))
    if not _contains_review_trigger(body):
        return None

    user = comment.get("user")
    commenter = str(user.get("login", "")) if isinstance(user, dict) else ""
    user_type = str(user.get("type", "")) if isinstance(user, dict) else ""
    if _is_bot_comment(commenter, user_type):
        return None

    owner_payload = repository.get("owner", {})
    owner = str(owner_payload.get("login", "")) if isinstance(owner_payload, dict) else ""
    repo = str(repository.get("name", ""))
    try:
        pull_number = int(issue.get("number", 0))
    except (TypeError, ValueError):
        return None
    if not owner or not repo or pull_number <= 0:
        return None
    if not _is_repo_allowed(owner, repo):
        return None

    pr_url = str(issue.get("html_url") or f"https://github.com/{owner}/{repo}/pull/{pull_number}")
    return PullRequestCommand(
        owner=owner,
        repo=repo,
        pull_number=pull_number,
        pr_url=pr_url,
        commenter=commenter,
        body=body,
    )


async def _is_duplicate_delivery(delivery_id: str) -> bool:
    cache_key = f"github:webhook:delivery:{delivery_id}"
    if await redis_cache.get(cache_key) is not None:
        return True
    await redis_cache.set(cache_key, True, ttl_seconds=_DELIVERY_CACHE_TTL_SECONDS)
    return False


def _decode_payload(raw_body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise GitHubWebhookError("Invalid GitHub webhook JSON payload", status_code=400) from exc
    if not isinstance(payload, dict):
        raise GitHubWebhookError("GitHub webhook payload must be an object", status_code=400)
    return payload


def _contains_review_trigger(body: str) -> bool:
    trigger = settings.github_review_trigger.strip().lower()
    if not trigger:
        return False
    normalized = " ".join(body.lower().split())
    return trigger in normalized


def _is_bot_comment(commenter: str, user_type: str) -> bool:
    bot_login = settings.github_bot_login.strip().lower()
    return user_type.lower() == "bot" or (bool(bot_login) and commenter.lower() == bot_login)


def _is_repo_allowed(owner: str, repo: str) -> bool:
    allowed = [item.lower() for item in settings.github_allowed_repos]
    return not allowed or f"{owner}/{repo}".lower() in allowed


async def _post_start_comment(command: PullRequestCommand, job_id: str) -> str | None:
    body = (
        "### ReviewMind 已开始审查\n\n"
        f"- PR: #{command.pull_number}\n"
        f"- Job: `{job_id}`\n"
        f"- Triggered by: @{command.commenter}\n\n"
        "完成后我会在本 PR 下追加审查报告。"
    )
    try:
        result = await post_pr_comment(
            owner=command.owner,
            repo=command.repo,
            pull_number=command.pull_number,
            body=body,
            github_token=settings.github_token,
        )
        return result.html_url
    except GitHubCommentError as exc:
        logger.warning("[WEBHOOK] Failed to post start comment for job=%s: %s", job_id, exc)
        return None


async def _post_final_comment_when_done(
    command: PullRequestCommand,
    job_id: str,
    service: ReviewJobService,
) -> None:
    timeout_seconds = max(settings.github_webhook_result_timeout_seconds, 1)
    poll_seconds = max(settings.github_webhook_result_poll_seconds, 0.2)
    deadline = asyncio.get_event_loop().time() + timeout_seconds

    while asyncio.get_event_loop().time() < deadline:
        detail = await service.get_job_detail(job_id)
        if detail.status in {ReviewJobStatus.completed, ReviewJobStatus.failed, ReviewJobStatus.cancelled}:
            body = _build_final_comment_body(detail)
            try:
                await post_pr_comment(
                    owner=command.owner,
                    repo=command.repo,
                    pull_number=command.pull_number,
                    body=body,
                    github_token=settings.github_token,
                )
            except GitHubCommentError as exc:
                logger.warning("[WEBHOOK] Failed to post final comment for job=%s: %s", job_id, exc)
            return
        await asyncio.sleep(poll_seconds)

    logger.warning("[WEBHOOK] Timed out waiting for review job=%s", job_id)


def _build_final_comment_body(detail) -> str:
    if detail.status == ReviewJobStatus.completed and detail.report and detail.report.review_comment:
        return detail.report.review_comment
    if detail.status == ReviewJobStatus.failed:
        reason = detail.error_message or "unknown error"
        return f"### ReviewMind 审查失败\n\nJob `{detail.job_id}` 执行失败：{reason}"
    if detail.status == ReviewJobStatus.cancelled:
        return f"### ReviewMind 审查已取消\n\nJob `{detail.job_id}` 已被取消。"
    return f"### ReviewMind 审查结束\n\nJob `{detail.job_id}` 状态：{detail.status}"
