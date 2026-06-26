from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assignment import AssignmentGroup, EvaluationCriterion


class GroupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_instructor(self, instructor_id: str) -> list[AssignmentGroup]:
        result = await self.session.execute(
            select(AssignmentGroup)
            .where(AssignmentGroup.instructor_id == instructor_id)
            .options(selectinload(AssignmentGroup.criteria), selectinload(AssignmentGroup.submissions))
            .order_by(AssignmentGroup.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id_for_instructor(self, group_id: str, instructor_id: str) -> AssignmentGroup | None:
        result = await self.session.execute(
            select(AssignmentGroup)
            .where(
                AssignmentGroup.id == group_id,
                AssignmentGroup.instructor_id == instructor_id,
            )
            .options(selectinload(AssignmentGroup.criteria), selectinload(AssignmentGroup.submissions))
        )
        return result.scalar_one_or_none()

    async def create(self, group: AssignmentGroup) -> AssignmentGroup:
        self.session.add(group)
        await self.session.flush()
        return group

    async def save(self, group: AssignmentGroup) -> AssignmentGroup:
        self.session.add(group)
        await self.session.flush()
        return group

    async def delete(self, group: AssignmentGroup) -> None:
        await self.session.execute(
            delete(AssignmentGroup)
            .where(AssignmentGroup.id == group.id)
            .execution_options(synchronize_session=False)
        )
        await self.session.flush()

    async def list_criteria(self, group_id: str) -> list[EvaluationCriterion]:
        result = await self.session.execute(
            select(EvaluationCriterion)
            .where(EvaluationCriterion.group_id == group_id)
            .order_by(EvaluationCriterion.sort_order.asc(), EvaluationCriterion.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_criterion_for_instructor(
        self, criterion_id: str, instructor_id: str
    ) -> EvaluationCriterion | None:
        result = await self.session.execute(
            select(EvaluationCriterion)
            .join(EvaluationCriterion.group)
            .where(
                EvaluationCriterion.id == criterion_id,
                AssignmentGroup.instructor_id == instructor_id,
            )
            .options(selectinload(EvaluationCriterion.group))
        )
        return result.scalar_one_or_none()

    async def create_criterion(self, criterion: EvaluationCriterion) -> EvaluationCriterion:
        self.session.add(criterion)
        await self.session.flush()
        return criterion

    async def save_criterion(self, criterion: EvaluationCriterion) -> EvaluationCriterion:
        self.session.add(criterion)
        await self.session.flush()
        return criterion

    async def delete_criterion(self, criterion: EvaluationCriterion) -> None:
        await self.session.execute(
            delete(EvaluationCriterion)
            .where(EvaluationCriterion.id == criterion.id)
            .execution_options(synchronize_session=False)
        )
        await self.session.flush()

    async def count_submissions(self, group_id: str) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(AssignmentGroup.submissions.property.mapper.class_).where(
                AssignmentGroup.submissions.property.mapper.class_.group_id == group_id
            )
        )
        return int(result.scalar_one())
