from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_instructor
from app.db.session import get_db
from app.schemas.groups import (
    AssignmentGroupCreate,
    AssignmentGroupDetailResponse,
    AssignmentGroupResponse,
    AssignmentGroupUpdate,
    EvaluationCriterionCreate,
    EvaluationCriterionResponse,
    EvaluationCriterionUpdate,
)
from app.services.group_service import GroupService

router = APIRouter(tags=["groups"])


def _group_detail(group) -> AssignmentGroupDetailResponse:
    criteria = [EvaluationCriterionResponse.model_validate(item) for item in group.criteria]
    weights_total = round(sum(float(item.weight) for item in group.criteria), 2)
    return AssignmentGroupDetailResponse(
        **AssignmentGroupResponse.model_validate(group).model_dump(),
        criteria=criteria,
        submissions_count=len(group.submissions),
        weights_total=weights_total,
        ready_for_evaluation=bool(criteria) and weights_total == 100,
    )


@router.get("/groups", response_model=list[AssignmentGroupDetailResponse])
async def list_groups(
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    groups = await GroupService(db).list_groups(current_instructor.id)
    return [_group_detail(group) for group in groups]


@router.post("/groups", response_model=AssignmentGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: AssignmentGroupCreate,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    group = await GroupService(db).create_group(current_instructor.id, payload)
    return AssignmentGroupResponse.model_validate(group)


@router.get("/groups/{group_id}", response_model=AssignmentGroupDetailResponse)
async def get_group(
    group_id: str,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    group = await GroupService(db).get_group(current_instructor.id, group_id)
    return _group_detail(group)


@router.patch("/groups/{group_id}", response_model=AssignmentGroupResponse)
async def update_group(
    group_id: str,
    payload: AssignmentGroupUpdate,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    group = await GroupService(db).update_group(current_instructor.id, group_id, payload)
    return AssignmentGroupResponse.model_validate(group)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    await GroupService(db).delete_group(current_instructor.id, group_id)


@router.get("/groups/{group_id}/criteria", response_model=list[EvaluationCriterionResponse])
async def list_criteria(
    group_id: str,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    criteria = await GroupService(db).list_criteria(current_instructor.id, group_id)
    return [EvaluationCriterionResponse.model_validate(item) for item in criteria]


@router.post(
    "/groups/{group_id}/criteria",
    response_model=EvaluationCriterionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_criterion(
    group_id: str,
    payload: EvaluationCriterionCreate,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    criterion = await GroupService(db).create_criterion(current_instructor.id, group_id, payload)
    return EvaluationCriterionResponse.model_validate(criterion)


@router.patch("/criteria/{criterion_id}", response_model=EvaluationCriterionResponse)
async def update_criterion(
    criterion_id: str,
    payload: EvaluationCriterionUpdate,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    criterion = await GroupService(db).update_criterion(current_instructor.id, criterion_id, payload)
    return EvaluationCriterionResponse.model_validate(criterion)


@router.delete("/criteria/{criterion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_criterion(
    criterion_id: str,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    await GroupService(db).delete_criterion(current_instructor.id, criterion_id)

