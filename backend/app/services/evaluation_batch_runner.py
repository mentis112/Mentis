import asyncio
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.exceptions import ExternalServiceError
from app.db.session import SessionLocal
from app.models.enums import SubmissionStatus
from app.schemas.evaluations import EvaluateSubmissionRequest


@dataclass
class _BatchRunState:
    instructor_id: str
    submission_ids: list[str]
    response_language: str
    max_parallel: int = 3
    rate_limit_retry_delays: list[int] = field(default_factory=lambda: [2, 5, 10])
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    cancel_requested: bool = False
    current_submission_id: str | None = None
    in_progress_submission_ids: list[str] = field(default_factory=list)
    completed_submission_ids: list[str] = field(default_factory=list)
    failed_submission_ids: list[str] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.submission_ids)

    @property
    def processed_count(self) -> int:
        return len(self.completed_submission_ids) + len(self.failed_submission_ids)

    @property
    def remaining_count(self) -> int:
        return max(self.total_count - self.processed_count, 0)


class EvaluationBatchRunner:
    _active_runs: dict[str, _BatchRunState] = {}
    _active_tasks: dict[str, asyncio.Task] = {}

    @classmethod
    def is_active(cls, instructor_id: str) -> bool:
        return instructor_id in cls._active_runs

    @classmethod
    def start(
        cls,
        *,
        instructor_id: str,
        submission_ids: list[str],
        response_language: str,
        max_parallel: int = 3,
        rate_limit_retry_delays: list[int] | None = None,
    ) -> bool:
        if cls.is_active(instructor_id):
            return False
        state = _BatchRunState(
            instructor_id=instructor_id,
            submission_ids=list(submission_ids),
            response_language=response_language,
            max_parallel=max(1, max_parallel),
            rate_limit_retry_delays=rate_limit_retry_delays or [2, 5, 10],
        )
        cls._active_runs[instructor_id] = state
        task = asyncio.create_task(
            cls._run(
                state=state,
            )
        )
        cls._active_tasks[instructor_id] = task
        task.add_done_callback(lambda _: cls._finalize(instructor_id))
        return True

    @classmethod
    def _finalize(cls, instructor_id: str) -> None:
        state = cls._active_runs.get(instructor_id)
        if not state:
            return
        state.current_submission_id = None
        state.in_progress_submission_ids = []
        state.finished_at = datetime.now(timezone.utc)
        cls._active_runs.pop(instructor_id, None)
        cls._active_tasks.pop(instructor_id, None)

    @classmethod
    def request_cancel(cls, instructor_id: str) -> bool:
        state = cls._active_runs.get(instructor_id)
        if not state:
            return False
        state.cancel_requested = True
        task = cls._active_tasks.get(instructor_id)
        if task and not task.done():
            task.cancel()
        return True

    @classmethod
    def get_status(cls, instructor_id: str) -> dict:
        state = cls._active_runs.get(instructor_id)
        if not state:
            return {
                "active": False,
                "cancel_requested": False,
                "total_count": 0,
                "processed_count": 0,
                "completed_count": 0,
                "failed_count": 0,
                "remaining_count": 0,
                "current_submission_id": None,
                "queued_submission_ids": [],
                "completed_submission_ids": [],
                "failed_submission_ids": [],
                "started_at": None,
                "finished_at": None,
            }

        return {
            "active": True,
            "cancel_requested": state.cancel_requested,
            "total_count": state.total_count,
            "processed_count": state.processed_count,
            "completed_count": len(state.completed_submission_ids),
            "failed_count": len(state.failed_submission_ids),
            "remaining_count": state.remaining_count,
            "current_submission_id": state.current_submission_id,
            "queued_submission_ids": list(state.submission_ids),
            "completed_submission_ids": list(state.completed_submission_ids),
            "failed_submission_ids": list(state.failed_submission_ids),
            "started_at": state.started_at,
            "finished_at": state.finished_at,
        }

    @classmethod
    async def _run(cls, *, state: _BatchRunState) -> None:
        queue: asyncio.Queue[str] = asyncio.Queue()
        for submission_id in state.submission_ids:
            queue.put_nowait(submission_id)

        worker_count = min(state.max_parallel, state.total_count)
        workers = [
            asyncio.create_task(cls._worker(state=state, queue=queue))
            for _ in range(worker_count)
        ]

        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            state.cancel_requested = True
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            raise
        finally:
            state.current_submission_id = None
            state.in_progress_submission_ids = []

    @classmethod
    async def _worker(cls, *, state: _BatchRunState, queue: asyncio.Queue[str]) -> None:
        while not state.cancel_requested:
            try:
                submission_id = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                await cls._evaluate_single_submission(state=state, submission_id=submission_id)
            finally:
                queue.task_done()

    @classmethod
    async def _evaluate_single_submission(cls, *, state: _BatchRunState, submission_id: str) -> None:
        from app.services.evaluation_service import EvaluationService

        state.current_submission_id = submission_id
        if submission_id not in state.in_progress_submission_ids:
            state.in_progress_submission_ids.append(submission_id)

        try:
            async with SessionLocal() as session:
                service = EvaluationService(session)
                max_attempts = len(state.rate_limit_retry_delays) + 1

                for attempt in range(1, max_attempts + 1):
                    try:
                        await service.evaluate_submission(
                            instructor_id=state.instructor_id,
                            submission_id=submission_id,
                            payload=EvaluateSubmissionRequest(),
                            response_language=state.response_language,
                        )
                        cls._append_unique(state.completed_submission_ids, submission_id)
                        return
                    except asyncio.CancelledError:
                        cls._append_unique(state.failed_submission_ids, submission_id)
                        try:
                            submission = await service.submission_repository.get_by_id_for_instructor(
                                submission_id,
                                state.instructor_id,
                            )
                            if submission:
                                submission.status = SubmissionStatus.FAILED
                                submission.error_message = "Evaluation cancelled by instructor"
                                submission.processed_at = datetime.now(timezone.utc)
                                await service.submission_repository.save_submission(submission)
                                await session.commit()
                        except Exception:
                            await session.rollback()
                        raise
                    except Exception as exc:
                        should_retry = cls._is_retryable_rate_limit_error(exc)
                        has_retry = attempt < max_attempts
                        if should_retry and has_retry and not state.cancel_requested:
                            delay = cls._resolve_retry_delay_seconds(
                                exc=exc,
                                fallback_delay=state.rate_limit_retry_delays[attempt - 1],
                            )
                            await asyncio.sleep(delay + random.uniform(0, 0.4))
                            continue
                        cls._append_unique(state.failed_submission_ids, submission_id)
                        return
        finally:
            state.in_progress_submission_ids = [
                in_progress_id
                for in_progress_id in state.in_progress_submission_ids
                if in_progress_id != submission_id
            ]
            if state.current_submission_id == submission_id:
                state.current_submission_id = (
                    state.in_progress_submission_ids[0] if state.in_progress_submission_ids else None
                )

    @staticmethod
    def _append_unique(target: list[str], value: str) -> None:
        if value not in target:
            target.append(value)

    @staticmethod
    def _is_retryable_rate_limit_error(exc: Exception) -> bool:
        if isinstance(exc, ExternalServiceError):
            provider_status = (exc.details or {}).get("status")
            if provider_status == 429:
                return True
            message = str(exc).lower()
            if "429" in message or "too many requests" in message or "rate limit" in message:
                return True
        return False

    @staticmethod
    def _resolve_retry_delay_seconds(*, exc: Exception, fallback_delay: int) -> int:
        if isinstance(exc, ExternalServiceError):
            details = exc.details or {}
            retry_after_seconds = details.get("retry_after_seconds")
            if isinstance(retry_after_seconds, (int, float)) and retry_after_seconds > 0:
                return max(int(retry_after_seconds), fallback_delay)

            provider_error = details.get("provider_error")
            if isinstance(provider_error, str):
                parsed = EvaluationBatchRunner._extract_seconds_from_rate_limit_message(provider_error)
                if parsed > 0:
                    return max(parsed, fallback_delay)

            parsed_from_message = EvaluationBatchRunner._extract_seconds_from_rate_limit_message(str(exc))
            if parsed_from_message > 0:
                return max(parsed_from_message, fallback_delay)
        return fallback_delay

    @staticmethod
    def _extract_seconds_from_rate_limit_message(text: str) -> int:
        match = re.search(r"(?:retry|try again)\s+in\s+([0-9]+(?:\.[0-9]+)?)s", text, re.IGNORECASE)
        if not match:
            return 0
        try:
            return max(int(float(match.group(1))), 1)
        except ValueError:
            return 0
