from fastapi.testclient import TestClient

from app.main import app
from app.models.review_job import ReviewJob
from app.schemas.review import ReviewJobStatus, ReviewReport, ReviewReportStats
from app.services.review_job_service import review_job_service
from app.services.review_job_store import ReviewJobStore


def install_store(store: ReviewJobStore):
    original_store = review_job_service._store
    review_job_service._store = store
    return original_store


def test_stream_returns_real_progress_events_for_running_job() -> None:
    store = ReviewJobStore()
    job = store.create(ReviewJob(job_id="rev_stream_1", pr_url="https://github.com/example/repo/pull/1"))
    store.update_status(job.job_id, ReviewJobStatus.running)
    store.add_progress_event(
        job.job_id,
        {"type": "progress", "step": "FETCH_PR", "percent": 30, "message": "GitHub PR 基本信息已拉取"},
    )
    original_store = install_store(store)
    client = TestClient(app)

    try:
        response = client.get(f"/api/v1/review/stream/{job.job_id}")
    finally:
        review_job_service._store = original_store

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: progress" in response.text
    assert '"step": "FETCH_PR"' in response.text
    assert "event: done" not in response.text


def test_stream_sends_done_for_completed_job() -> None:
    store = ReviewJobStore()
    report = ReviewReport(
        summary="done",
        risk_level="LOW",
        stats=ReviewReportStats(),
        changed_files=[],
        changed_symbols=[],
        findings=[],
        review_comment="done",
    )
    job = store.create(ReviewJob(job_id="rev_stream_2", pr_url="https://github.com/example/repo/pull/2"))
    store.update_status(job.job_id, ReviewJobStatus.running)
    store.update_status(job.job_id, ReviewJobStatus.completed, report=report)
    original_store = install_store(store)
    client = TestClient(app)

    try:
        response = client.get(f"/api/v1/review/stream/{job.job_id}")
    finally:
        review_job_service._store = original_store

    assert response.status_code == 200
    assert "event: done" in response.text
    assert '"status": "completed"' in response.text


def test_stream_sends_warning_and_done_for_failed_job() -> None:
    store = ReviewJobStore()
    job = store.create(ReviewJob(job_id="rev_stream_3", pr_url="https://github.com/example/repo/pull/3"))
    store.update_status(job.job_id, ReviewJobStatus.failed, error_message="GitHub pull request was not found")
    original_store = install_store(store)
    client = TestClient(app)

    try:
        response = client.get(f"/api/v1/review/stream/{job.job_id}")
    finally:
        review_job_service._store = original_store

    assert response.status_code == 200
    assert "event: warning" in response.text
    assert "GitHub pull request was not found" in response.text
    assert "event: done" in response.text


def test_stream_returns_404_for_missing_job() -> None:
    store = ReviewJobStore()
    original_store = install_store(store)
    client = TestClient(app)

    try:
        response = client.get("/api/v1/review/stream/missing")
    finally:
        review_job_service._store = original_store

    assert response.status_code == 404