from fastapi.testclient import TestClient

from app.main import app
from app.api import review as review_api
from app.models.review_job import ReviewJob
from app.schemas.github import GitHubPullRequestFile
from app.schemas.review import (
    ChangedFile,
    ReviewJobStatus,
    ReviewReport,
    ReviewReportStats,
)
from app.services.review_job_service import review_job_service
from app.services.review_job_store import ReviewJobStore


def install_store(store: ReviewJobStore):
    original_store = review_job_service._store
    review_job_service._store = store
    return original_store


def _make_report() -> ReviewReport:
    return ReviewReport(
        summary="Found 2 issues",
        risk_level="MEDIUM",
        stats=ReviewReportStats(critical=0, high=1, medium=1, low=0, suggestion=0),
        changed_files=[],
        changed_symbols=[],
        findings=[],
        review_comment="## AI Review Summary\n\nFound 2 issues.",
    )


def test_detail_returns_full_report_for_completed_job() -> None:
    store = ReviewJobStore()
    job = store.create(ReviewJob(
        job_id="rev_detail_1",
        pr_url="https://github.com/example/repo/pull/10",
    ))
    store.save_pr_info(job.job_id, {
        "owner": "example",
        "repo": "repo",
        "pull_number": 10,
        "title": "Fix login bug",
        "author": "alice",
        "state": "open",
        "base": {"ref": "main", "sha": "abc"},
        "head": {"ref": "fix/login", "sha": "def"},
        "changed_files": 3,
        "additions": 20,
        "deletions": 5,
        "html_url": "https://github.com/example/repo/pull/10",
    })
    store.update_status(job.job_id, ReviewJobStatus.running)
    report = _make_report()
    store.update_status(job.job_id, ReviewJobStatus.completed, report=report)

    original_store = install_store(store)
    client = TestClient(app)
    try:
        response = client.get("/api/v1/review/jobs/rev_detail_1")
    finally:
        review_job_service._store = original_store

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 20000
    data = body["data"]
    assert data["job_id"] == "rev_detail_1"
    assert data["status"] == "completed"
    assert data["pr"]["owner"] == "example"
    assert data["pr"]["number"] == 10
    assert data["report"]["summary"] == "Found 2 issues"
    assert data["report"]["risk_level"] == "MEDIUM"
    assert data["completed_at"] is not None
    assert data["error_message"] is None


def test_detail_hydrates_missing_patch_for_completed_job() -> None:
    store = ReviewJobStore()
    job = store.create(ReviewJob(
        job_id="rev_detail_patch",
        pr_url="https://github.com/example/repo/pull/12",
    ))
    store.save_pr_info(job.job_id, {
        "owner": "example",
        "repo": "repo",
        "pull_number": 12,
        "title": "Update package",
        "author": "alice",
        "state": "open",
        "base": {"ref": "main", "sha": "abc"},
        "head": {"ref": "feature/pkg", "sha": "def"},
        "changed_files": 1,
        "additions": 1,
        "deletions": 1,
        "html_url": "https://github.com/example/repo/pull/12",
    })
    report = ReviewReport(
        summary="Patch is missing",
        risk_level="LOW",
        stats=ReviewReportStats(),
        changed_files=[
            ChangedFile(
                filename="package.json",
                status="modified",
                additions=1,
                deletions=1,
                patch=None,
            ),
        ],
        changed_symbols=[],
        findings=[],
        review_comment="## AI Review Summary",
    )
    store.update_status(job.job_id, ReviewJobStatus.running)
    store.update_status(job.job_id, ReviewJobStatus.completed, report=report)

    class FakeGitHubClient:
        async def fetch_pull_request_files(self, pr_ref):
            return [
                GitHubPullRequestFile(
                    filename="package.json",
                    status="modified",
                    additions=1,
                    deletions=1,
                    patch="@@ -1 +1 @@\n-old\n+new",
                ),
            ]

    original_store = install_store(store)
    original_github_client = review_api.github_client
    review_api.github_client = FakeGitHubClient()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/review/jobs/rev_detail_patch")
    finally:
        review_api.github_client = original_github_client
        review_job_service._store = original_store

    assert response.status_code == 200
    changed_file = response.json()["data"]["report"]["changed_files"][0]
    assert changed_file["patch"] == "@@ -1 +1 @@\n-old\n+new"
    assert changed_file["changes"] == 2


def test_detail_returns_progress_for_running_job() -> None:
    store = ReviewJobStore()
    job = store.create(ReviewJob(
        job_id="rev_detail_2",
        pr_url="https://github.com/example/repo/pull/11",
    ))
    store.update_status(job.job_id, ReviewJobStatus.running)
    store.add_progress_event(
        job.job_id,
        {"type": "progress", "step": "DIFF_FILTER", "percent": 65, "message": "Diff 降噪已完成"},
    )

    original_store = install_store(store)
    client = TestClient(app)
    try:
        response = client.get("/api/v1/review/jobs/rev_detail_2")
    finally:
        review_job_service._store = original_store

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "running"
    assert data["progress"] is not None
    assert data["progress"]["step"] == "DIFF_FILTER"
    assert data["report"] is None


def test_detail_returns_error_for_failed_job() -> None:
    store = ReviewJobStore()
    job = store.create(ReviewJob(
        job_id="rev_detail_3",
        pr_url="https://github.com/example/repo/pull/404",
    ))
    store.update_status(job.job_id, ReviewJobStatus.failed, error_message="GitHub pull request was not found")

    original_store = install_store(store)
    client = TestClient(app)
    try:
        response = client.get("/api/v1/review/jobs/rev_detail_3")
    finally:
        review_job_service._store = original_store

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "failed"
    assert data["error_message"] == "GitHub pull request was not found"
    assert data["report"] is None


def test_detail_returns_404_for_missing_job() -> None:
    store = ReviewJobStore()
    original_store = install_store(store)
    client = TestClient(app)
    try:
        response = client.get("/api/v1/review/jobs/rev_missing")
    finally:
        review_job_service._store = original_store

    assert response.status_code == 404
