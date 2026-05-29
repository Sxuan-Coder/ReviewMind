"""Tests for ReviewTaskRunner."""

import asyncio

import pytest

from app.models.review_job import ReviewJob
from app.schemas.github import GitHubBranchRef, GitHubPullRequestFile, GitHubPullRequestInfo
from app.schemas.review import CreateReviewJobRequest, ReviewJobStatus
from app.services.github_client import GitHubClientError
from app.services.review_job_service import ReviewJobService
from app.services.review_job_store import ReviewJobStore
from app.services.review_pipeline import ReviewPipeline
from app.services.review_task_runner import ReviewTaskRunner


class SlowMockGitHubClient:
    def __init__(self, delay: float = 0.05):
        self._delay = delay

    async def fetch_pull_request(self, pr_ref):
        await asyncio.sleep(self._delay)
        return GitHubPullRequestInfo(
            owner=pr_ref.owner,
            repo=pr_ref.repo,
            pull_number=pr_ref.pull_number,
            title="Test PR",
            author="tester",
            state="open",
            base=GitHubBranchRef(ref="main", sha="abc"),
            head=GitHubBranchRef(ref="feature", sha="def"),
            changed_files=1,
            additions=5,
            deletions=2,
            html_url=pr_ref.html_url,
        )

    async def fetch_pull_request_files(self, pr_ref):
        await asyncio.sleep(self._delay)
        return [
            GitHubPullRequestFile(
                filename="src/example.py",
                status="modified",
                additions=5,
                deletions=2,
                patch="@@ -1,3 +1,6 @@\n def hello():\n-    return 1\n+    return 2\n+    x = 3\n",
            ),
        ]


class FailingMockGitHubClient:
    async def fetch_pull_request(self, pr_ref):
        raise GitHubClientError("Not found", status_code=404)

    async def fetch_pull_request_files(self, pr_ref):
        return []


@pytest.mark.anyio
async def test_task_runner_submits_and_completes_background_task() -> None:
    store = ReviewJobStore()
    runner = ReviewTaskRunner(store)
    pipeline = ReviewPipeline(store, SlowMockGitHubClient(delay=0.02))

    job = store.create(ReviewJob(job_id="bg_1", pr_url="https://github.com/example/repo/pull/1"))

    assert not runner.is_running("bg_1")

    await runner.submit(job, lambda j: pipeline.run(j))

    assert runner.is_running("bg_1")
    assert runner.running_count() == 1

    await asyncio.sleep(0.2)

    assert not runner.is_running("bg_1")
    assert runner.running_count() == 0

    saved = store.get("bg_1")
    assert saved.status == ReviewJobStatus.completed
    assert saved.report is not None


@pytest.mark.anyio
async def test_task_runner_prevents_duplicate_submission() -> None:
    store = ReviewJobStore()
    runner = ReviewTaskRunner(store)
    pipeline = ReviewPipeline(store, SlowMockGitHubClient(delay=0.1))

    job = store.create(ReviewJob(job_id="bg_dup", pr_url="https://github.com/example/repo/pull/1"))
    await runner.submit(job, lambda j: pipeline.run(j))

    with pytest.raises(RuntimeError, match="already running"):
        await runner.submit(job, lambda j: pipeline.run(j))

    await asyncio.sleep(0.3)


@pytest.mark.anyio
async def test_task_runner_handles_pipeline_failure_gracefully() -> None:
    store = ReviewJobStore()
    runner = ReviewTaskRunner(store)
    pipeline = ReviewPipeline(store, FailingMockGitHubClient())

    job = store.create(ReviewJob(job_id="bg_fail", pr_url="https://github.com/example/repo/pull/404"))
    await runner.submit(job, lambda j: pipeline.run(j))

    await asyncio.sleep(0.1)

    assert not runner.is_running("bg_fail")
    saved = store.get("bg_fail")
    assert saved.status == ReviewJobStatus.failed


@pytest.mark.anyio
async def test_create_job_returns_pending_immediately() -> None:
    store = ReviewJobStore()
    runner = ReviewTaskRunner(store)
    pipeline = ReviewPipeline(store, SlowMockGitHubClient(delay=0.1))

    service = ReviewJobService(store, pipeline, task_runner=runner)
    request = CreateReviewJobRequest(pr_url="https://github.com/example/repo/pull/99")

    start = asyncio.get_event_loop().time()
    response = await service.create_job(request)
    elapsed = asyncio.get_event_loop().time() - start

    assert elapsed < 0.05
    assert response.status == ReviewJobStatus.pending
    assert response.job_id.startswith("rev_")

    await asyncio.sleep(0.3)
    saved = store.get(response.job_id)
    assert saved.status == ReviewJobStatus.completed