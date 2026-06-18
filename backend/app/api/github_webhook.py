from fastapi import APIRouter, Header, HTTPException, Request

from app.schemas.common import ApiResponse, success_response
from app.services.github_webhook import GitHubWebhookError, handle_github_webhook

router = APIRouter(prefix="/github", tags=["github"])


@router.post("/webhook", response_model=ApiResponse[dict])
async def receive_github_webhook(
    request: Request,
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
) -> ApiResponse[dict]:
    """接收 GitHub Webhook，并在 PR 评论命中触发词时启动自动审查。"""
    raw_body = await request.body()
    try:
        result = await handle_github_webhook(
            event=x_github_event,
            delivery_id=x_github_delivery,
            signature=x_hub_signature_256,
            raw_body=raw_body,
        )
    except GitHubWebhookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return success_response(
        {
            "accepted": result.accepted,
            "ignored": result.ignored,
            "reason": result.reason,
            "job_id": result.job_id,
            "pr_url": result.pr_url,
            "start_comment_url": result.start_comment_url,
        },
        message=result.reason,
        code=20200 if result.accepted else 20000,
    )
