from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment import AssignmentGroup
from app.models.enums import ProviderUsageStatus, SubmissionStatus
from app.models.evaluation import EvaluationResult
from app.models.provider import ProviderUsageLog
from app.models.submission import Submission


class DashboardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def summary(self, instructor_id: str) -> dict:
        total_groups = await self._scalar(
            select(func.count(AssignmentGroup.id)).where(AssignmentGroup.instructor_id == instructor_id)
        )
        total_submissions = await self._scalar(
            select(func.count(Submission.id))
            .join(Submission.group)
            .where(AssignmentGroup.instructor_id == instructor_id)
        )
        pending_submissions = await self._count_submissions_by_statuses(
            instructor_id,
            [
                SubmissionStatus.PENDING,
                SubmissionStatus.QUEUED,
                SubmissionStatus.PROCESSING,
                SubmissionStatus.PARTIALLY_PROCESSED,
            ],
        )
        completed_submissions = await self._count_submissions_by_status(
            instructor_id, SubmissionStatus.COMPLETED
        )
        failed_submissions = await self._count_submissions_by_status(instructor_id, SubmissionStatus.FAILED)
        completed_evaluations = await self._scalar(
            select(func.count(EvaluationResult.id))
            .join(EvaluationResult.submission)
            .join(Submission.group)
            .where(AssignmentGroup.instructor_id == instructor_id)
        )
        avg_adjusted = await self._scalar(
            select(func.avg(EvaluationResult.final_adjusted_score))
            .join(EvaluationResult.submission)
            .join(Submission.group)
            .where(AssignmentGroup.instructor_id == instructor_id)
        )

        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        usage_logs = await self._usage_logs(instructor_id, month_start)
        evaluations_by_provider = dict(Counter(log.provider_name.value for log in usage_logs if log.submission_id))
        provider_failures_this_month = sum(
            1 for log in usage_logs if log.status == ProviderUsageStatus.FAILED
        )
        usage_today = sum(1 for log in usage_logs if log.created_at >= day_start)
        usage_this_month = len(usage_logs)

        return {
            "total_groups": int(total_groups or 0),
            "total_submissions": int(total_submissions or 0),
            "pending_submissions": int(pending_submissions or 0),
            "completed_submissions": int(completed_submissions or 0),
            "failed_submissions": int(failed_submissions or 0),
            "completed_evaluations": int(completed_evaluations or 0),
            "average_adjusted_score": float(avg_adjusted) if avg_adjusted is not None else None,
            "evaluations_by_provider": evaluations_by_provider,
            "provider_failures_this_month": provider_failures_this_month,
            "usage_today": usage_today,
            "usage_this_month": usage_this_month,
        }

    async def _count_submissions_by_status(self, instructor_id: str, status: SubmissionStatus) -> int:
        return await self._count_submissions_by_statuses(instructor_id, [status])

    async def _count_submissions_by_statuses(
        self, instructor_id: str, statuses: list[SubmissionStatus]
    ) -> int:
        return int(
            await self._scalar(
                select(func.count(Submission.id))
                .join(Submission.group)
                .where(
                    AssignmentGroup.instructor_id == instructor_id,
                    Submission.status.in_(statuses),
                )
            )
            or 0
        )

    async def _usage_logs(self, instructor_id: str, since: datetime) -> list[ProviderUsageLog]:
        result = await self.session.execute(
            select(ProviderUsageLog).where(
                ProviderUsageLog.instructor_id == instructor_id,
                ProviderUsageLog.created_at >= since,
            )
        )
        return list(result.scalars().all())

    async def _scalar(self, statement):
        result = await self.session.execute(statement)
        return result.scalar_one()
