from fastapi.testclient import TestClient

from app.main import app


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
    client = TestClient(app)
    response = client.post(
        "/api/v1/review/jobs",
        json={"pr_url": "https://github.com/Sxuan-Coder/ReviewMind/pull/1"},
    )

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