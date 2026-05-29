from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.review import review_router, github_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(review_router)
api_router.include_router(github_router)