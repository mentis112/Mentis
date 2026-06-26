from datetime import datetime, timezone

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assignment import AssignmentGroup
from app.models.evaluation import CriterionScore, EvaluationResult
from app.models.enums import SubmissionStatus
from app.models.submission import Submission, SubmissionContentCache, UploadBatch


class SubmissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_batch(self, batch: UploadBatch) -> UploadBatch:
        self.session.add(batch)
        await self.session.flush()
        return batch

    async def save_batch(self, batch: UploadBatch) -> UploadBatch:
        self.session.add(batch)
        await self.session.flush()
        return batch

    async def create_submission(self, submission: Submission) -> Submission:
        self.session.add(submission)
        await self.session.flush()
        return submission

    async def save_submission(self, submission: Submission) -> Submission:
        self.session.add(submission)
        await self.session.flush()
        return submission

    async def create_content_cache(self, cache: SubmissionContentCache) -> SubmissionContentCache:
        self.session.add(cache)
        await self.session.flush()
        return cache

    async def get_by_id_for_instructor(self, submission_id: str, instructor_id: str) -> Submission | None:
        result = await self.session.execute(
            select(Submission)
            .join(Submission.group)
            .where(
                Submission.id == submission_id,
                AssignmentGroup.instructor_id == instructor_id,
            )
            .options(
                selectinload(Submission.group).selectinload(AssignmentGroup.criteria),
                selectinload(Submission.content_cache),
                selectinload(Submission.evaluations),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_instructor(
        self,
        instructor_id: str,
        *,
        group_id: str | None = None,
        missing_student_id_only: bool = False,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[Submission], int]:
        filters = [AssignmentGroup.instructor_id == instructor_id]
        if group_id:
            filters.append(Submission.group_id == group_id)
        if missing_student_id_only:
            filters.append(func.length(func.trim(Submission.student_id)) == 0)

        base_query = select(Submission).join(Submission.group).where(*filters)
        total = await self._count_query(base_query)
        result = await self.session.execute(
            base_query
            .options(selectinload(Submission.group))
            .order_by(Submission.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def list_for_group(self, group_id: str) -> list[Submission]:
        result = await self.session.execute(
            select(Submission)
            .where(Submission.group_id == group_id)
            .options(selectinload(Submission.content_cache), selectinload(Submission.evaluations))
            .order_by(Submission.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_report_for_instructor(
        self,
        instructor_id: str,
        *,
        group_id: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[Submission], int]:
        filters = [AssignmentGroup.instructor_id == instructor_id]
        if group_id:
            filters.append(Submission.group_id == group_id)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Submission.original_filename.ilike(pattern),
                    Submission.student_id.ilike(pattern),
                    cast(Submission.status, String).ilike(pattern),
                )
            )

        base_query = select(Submission).join(Submission.group).where(*filters)
        total = await self._count_query(base_query)
        result = await self.session.execute(
            base_query
            .options(
                selectinload(Submission.group).selectinload(AssignmentGroup.criteria),
                selectinload(Submission.evaluations)
                .selectinload(EvaluationResult.criterion_scores)
                .selectinload(CriterionScore.criterion),
            )
            .order_by(Submission.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def list_evaluatable_ids_for_group(self, instructor_id: str, group_id: str) -> list[str]:
        result = await self.session.execute(
            select(Submission.id)
            .join(Submission.group)
            .where(
                AssignmentGroup.instructor_id == instructor_id,
                Submission.group_id == group_id,
                Submission.status.in_(
                    [
                        SubmissionStatus.PENDING,
                        SubmissionStatus.FAILED,
                        SubmissionStatus.QUEUED,
                    ]
                ),
                func.length(func.trim(Submission.student_id)) > 0,
            )
            .order_by(Submission.created_at.desc())
        )
        return list(result.scalars().all())

    async def mark_processed(self, submission: Submission) -> Submission:
        submission.processed_at = datetime.now(timezone.utc)
        self.session.add(submission)
        await self.session.flush()
        return submission

    async def _count_query(self, query) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(query.order_by(None).subquery())
        )
        return int(result.scalar_one() or 0)
