from fastapi import APIRouter

from app.schemas.common import ApiResponse, success_response

router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse[dict[str, str]])
async def health_check() -> ApiResponse[dict[str, str]]:
    return success_response({"status": "ok", "service": "reviewmind-api", "version": "1.0.0"})