import shutil
from pathlib import Path

from app.core.config import get_settings
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.assignment import AssignmentGroup, EvaluationCriterion
from app.repositories.group_repository import GroupRepository
from app.schemas.groups import (
    AssignmentGroupCreate,
    AssignmentGroupUpdate,
    EvaluationCriterionCreate,
    EvaluationCriterionUpdate,
)
from app.services.audit_service import AuditService


class GroupService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = GroupRepository(session)
        self.audit_service = AuditService(session)

    async def list_groups(self, instructor_id: str) -> list[AssignmentGroup]:
        return await self.repository.list_for_instructor(instructor_id)

    async def get_group(self, instructor_id: str, group_id: str) -> AssignmentGroup:
        group = await self.repository.get_by_id_for_instructor(group_id, instructor_id)
        if not group:
            raise NotFoundError("Assignment group not found")
        return group

    async def create_group(self, instructor_id: str, payload: AssignmentGroupCreate) -> AssignmentGroup:
        group = AssignmentGroup(
            instructor_id=instructor_id,
            name=payload.name.strip(),
            description=payload.description,
            grade_scale=payload.grade_scale,
            enable_auto_score_adjustment=payload.enable_auto_score_adjustment,
            is_active=payload.is_active,
        )
        await self.repository.create(group)
        await self.audit_service.log(
            instructor_id=instructor_id,
            action="group.created",
            entity_type="assignment_group",
            entity_id=group.id,
        )
        await self.session.commit()
        return group

    async def update_group(
        self, instructor_id: str, group_id: str, payload: AssignmentGroupUpdate
    ) -> AssignmentGroup:
        group = await self.get_group(instructor_id, group_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(group, field, value)
        await self.repository.save(group)
        await self.audit_service.log(
            instructor_id=instructor_id,
            action="group.updated",
            entity_type="assignment_group",
            entity_id=group.id,
        )
        await self.session.commit()
        return group

    async def delete_group(self, instructor_id: str, group_id: str) -> None:
        group = await self.get_group(instructor_id, group_id)
        group_storage_path = self._get_group_storage_path(instructor_id, group.id)
        await self.repository.delete(group)
        await self.audit_service.log(
            instructor_id=instructor_id,
            action="group.deleted",
            entity_type="assignment_group",
            entity_id=group_id,
        )
        await self.session.commit()
        shutil.rmtree(group_storage_path, ignore_errors=True)

    async def list_criteria(self, instructor_id: str, group_id: str) -> list[EvaluationCriterion]:
        group = await self.get_group(instructor_id, group_id)
        return list(group.criteria)

    async def create_criterion(
        self, instructor_id: str, group_id: str, payload: EvaluationCriterionCreate
    ) -> EvaluationCriterion:
        group = await self.get_group(instructor_id, group_id)
        self._validate_weight_limit(group.criteria, payload.weight, group.grade_scale)
        criterion = EvaluationCriterion(
            group_id=group.id,
            name=payload.name.strip(),
            weight=payload.weight,
            description=payload.description,
            is_manual=payload.is_manual,
            sort_order=payload.sort_order,
        )
        await self.repository.create_criterion(criterion)
        await self.audit_service.log(
            instructor_id=instructor_id,
            action="criterion.created",
            entity_type="evaluation_criterion",
            entity_id=criterion.id,
        )
        await self.session.commit()
        return criterion

    async def update_criterion(
        self, instructor_id: str, criterion_id: str, payload: EvaluationCriterionUpdate
    ) -> EvaluationCriterion:
        criterion = await self.repository.get_criterion_for_instructor(criterion_id, instructor_id)
        if not criterion:
            raise NotFoundError("Evaluation criterion not found")

        incoming = payload.model_dump(exclude_unset=True)
        if "weight" in incoming:
            siblings = [item for item in criterion.group.criteria if item.id != criterion.id]
            self._validate_weight_limit(siblings, incoming["weight"], criterion.group.grade_scale)
        for field, value in incoming.items():
            setattr(criterion, field, value)
        await self.repository.save_criterion(criterion)
        await self.audit_service.log(
            instructor_id=instructor_id,
            action="criterion.updated",
            entity_type="evaluation_criterion",
            entity_id=criterion.id,
        )
        await self.session.commit()
        return criterion

    async def delete_criterion(self, instructor_id: str, criterion_id: str) -> None:
        criterion = await self.repository.get_criterion_for_instructor(criterion_id, instructor_id)
        if not criterion:
            raise NotFoundError("Evaluation criterion not found")
        await self.repository.delete_criterion(criterion)
        await self.audit_service.log(
            instructor_id=instructor_id,
            action="criterion.deleted",
            entity_type="evaluation_criterion",
            entity_id=criterion.id,
        )
        await self.session.commit()

    def ensure_group_ready_for_evaluation(self, group: AssignmentGroup) -> None:
        if not group.criteria:
            raise ValidationError("At least one evaluation criterion is required before evaluation")
        total = round(sum(float(criterion.weight) for criterion in group.criteria), 2)
        if total != group.grade_scale:
            raise ValidationError(f"Criteria weights must total exactly {group.grade_scale} before evaluation", {"total": total, "expected": group.grade_scale})

    def _validate_weight_limit(self, criteria: list[EvaluationCriterion], new_weight: float, grade_scale: int = None) -> None:
        total = sum(float(item.weight) for item in criteria) + float(new_weight)
        max_weight = grade_scale if grade_scale else (criteria[0].group.grade_scale if criteria else 100)
        if total > max_weight:
            raise ValidationError(f"Criteria weights cannot exceed {max_weight}", {"proposed_total": total, "max": max_weight})

    def _get_group_storage_path(self, instructor_id: str, group_id: str) -> Path:
        return get_settings().storage_root / instructor_id / group_id
