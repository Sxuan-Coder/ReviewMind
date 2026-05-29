from app.models.review_job import ReviewJob
from app.schemas.review import ReviewJobStatus, ReviewReport


class ReviewJobNotFoundError(Exception):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"Review job not found: {job_id}")
        self.job_id = job_id


class InvalidReviewJobTransitionError(Exception):
    def __init__(self, current: ReviewJobStatus, target: ReviewJobStatus) -> None:
        super().__init__(f"Invalid review job transition: {current} -> {target}")
        self.current = current
        self.target = target


class ReviewJobStore:
    allowed_transitions: dict[ReviewJobStatus, set[ReviewJobStatus]] = {
        ReviewJobStatus.pending: {ReviewJobStatus.running, ReviewJobStatus.failed},
        ReviewJobStatus.running: {ReviewJobStatus.completed, ReviewJobStatus.failed},
        ReviewJobStatus.completed: set(),
        ReviewJobStatus.failed: set(),
    }

    def __init__(self) -> None:
        self._jobs: dict[str, ReviewJob] = {}

    def create(self, job: ReviewJob) -> ReviewJob:
        self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> ReviewJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise ReviewJobNotFoundError(job_id)
        return job

    def update_status(
        self,
        job_id: str,
        status: ReviewJobStatus,
        *,
        error_message: str | None = None,
        report: ReviewReport | None = None,
    ) -> ReviewJob:
        job = self.get(job_id)
        allowed = self.allowed_transitions[job.status]
        if status not in allowed:
            raise InvalidReviewJobTransitionError(job.status, status)

        job.status = status
        job.error_message = error_message
        if report is not None:
            job.report = report
        job.mark_updated()
        return job

    def add_progress_event(self, job_id: str, event: dict[str, object]) -> ReviewJob:
        job = self.get(job_id)
        job.progress_events.append(event)
        job.mark_updated()
        return job

    def save_pipeline_result(self, job_id: str, result: object) -> ReviewJob:
        job = self.get(job_id)
        if hasattr(result, "__dict__"):
            job.pipeline_result = dict(result.__dict__)
        else:
            job.pipeline_result = {"result": result}
        job.mark_updated()
        return job


review_job_store = ReviewJobStore()