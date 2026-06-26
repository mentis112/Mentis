from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assignment import AssignmentGroup
from app.models.evaluation import CriterionScore, EvaluationResult, ManualAdjustmentHistory
from app.models.submission import Submission


class EvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_submission(
        self, submission_id: str, instructor_id: str
    ) -> list[EvaluationResult]:
        result = await self.session.execute(
            select(EvaluationResult)
            .join(EvaluationResult.submission)
            .join(Submission.group)
            .where(
                EvaluationResult.submission_id == submission_id,
                AssignmentGroup.instructor_id == instructor_id,
            )
            .options(selectinload(EvaluationResult.submission).selectinload(Submission.group))
            .order_by(EvaluationResult.evaluation_number.desc())
        )
        return list(result.scalars().all())

    async def list_for_instructor(self, instructor_id: str) -> list[EvaluationResult]:
        result = await self.session.execute(
            select(EvaluationResult)
            .join(EvaluationResult.submission)
            .join(Submission.group)
            .where(AssignmentGroup.instructor_id == instructor_id)
            .options(
                selectinload(EvaluationResult.submission).selectinload(Submission.group),
                selectinload(EvaluationResult.criterion_scores).selectinload(CriterionScore.criterion),
            )
            .order_by(EvaluationResult.created_at.desc(), EvaluationResult.evaluation_number.desc())
        )
        return list(result.scalars().all())

    async def get_by_id_for_instructor(
        self, evaluation_id: str, instructor_id: str
    ) -> EvaluationResult | None:
        result = await self.session.execute(
            select(EvaluationResult)
            .join(EvaluationResult.submission)
            .join(Submission.group)
            .where(
                EvaluationResult.id == evaluation_id,
                AssignmentGroup.instructor_id == instructor_id,
            )
            .options(
                selectinload(EvaluationResult.criterion_scores).selectinload(CriterionScore.criterion),
                selectinload(EvaluationResult.submission)
                .selectinload(Submission.group)
                .selectinload(AssignmentGroup.criteria),
            )
        )
        return result.scalar_one_or_none()

    async def next_evaluation_number(self, submission_id: str) -> int:
        result = await self.session.execute(
            select(func.count(EvaluationResult.id)).where(EvaluationResult.submission_id == submission_id)
        )
        return int(result.scalar_one()) + 1

    async def clear_latest_flags(self, submission_id: str) -> None:
        await self.session.execute(
            update(EvaluationResult)
            .where(
                EvaluationResult.submission_id == submission_id,
                EvaluationResult.is_latest.is_(True),
            )
            .values(is_latest=False)
        )

    async def create_result(self, result_model: EvaluationResult) -> EvaluationResult:
        self.session.add(result_model)
        await self.session.flush()
        return result_model

    async def create_criterion_score(self, score: CriterionScore) -> CriterionScore:
        self.session.add(score)
        await self.session.flush()
        return score

    async def save_result(self, result_model: EvaluationResult) -> EvaluationResult:
        self.session.add(result_model)
        await self.session.flush()
        return result_model

    async def save_criterion_score(self, score: CriterionScore) -> CriterionScore:
        self.session.add(score)
        await self.session.flush()
        return score

    async def create_adjustment_history(
        self, adjustment: ManualAdjustmentHistory
    ) -> ManualAdjustmentHistory:
        self.session.add(adjustment)
        await self.session.flush()
        return adjustment
