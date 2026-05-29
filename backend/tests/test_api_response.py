from fastapi.testclient import TestClient

from app.main import app
from app.services.review_job_service import review_job_service
from app.services.review_pipeline import ReviewPipelineResult


class NoopPipeline:
    async def run(self, job):
        return ReviewPipelineResult(pr_info={}, filtered_files={}, parsed_diff=[])


def test_health_uses_unified_response() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "code": 20000,
        "message": "success",
        "data": {"status": "ok", "service": "reviewmind-api"},
    }


def test_create_review_job_uses_created_response() -> None:
    original_pipeline = review_job_service._pipeline
    review_job_service._pipeline = NoopPipeline()
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/review/jobs",
            json={"pr_url": "https://github.com/Sxuan-Coder/ReviewMind/pull/1"},
        )
    finally:
        review_job_service._pipeline = original_pipeline

    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 20200
    assert body["message"] == "review job created"
    assert body["data"]["status"] == "pending"
    assert body["data"]["stream_url"].startswith("/api/v1/review/stream/rev_")


def test_validation_error_uses_unified_response() -> None:
    client = TestClient(app)
    response = client.post("/api/v1/review/jobs", json={"pr_url": "not-a-url"})

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == 42200
    assert body["message"]
    assert body["data"] is None