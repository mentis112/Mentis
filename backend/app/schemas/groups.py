from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AssignmentGroupCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    grade_scale: int = Field(ge=1, le=1000)
    is_active: bool = True


class AssignmentGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    grade_scale: int | None = Field(default=None, ge=1, le=1000)
    is_active: bool | None = None


class EvaluationCriterionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    weight: float = Field(gt=0, le=100)
    description: str | None = Field(default=None, max_length=4000)
    is_manual: bool = False
    sort_order: int = Field(default=0, ge=0, le=10_000)


class EvaluationCriterionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    weight: float | None = Field(default=None, gt=0, le=100)
    description: str | None = Field(default=None, max_length=4000)
    is_manual: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)


class EvaluationCriterionResponse(ORMModel):
    id: str
    group_id: str
    name: str
    weight: float
    description: str | None
    is_manual: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class AssignmentGroupResponse(ORMModel):
    id: str
    instructor_id: str
    name: str
    description: str | None
    grade_scale: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AssignmentGroupDetailResponse(AssignmentGroupResponse):
    criteria: list[EvaluationCriterionResponse]
    submissions_count: int = 0
    weights_total: float = 0
    ready_for_evaluation: bool = False

