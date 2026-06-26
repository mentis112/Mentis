from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ProviderName
from app.schemas.common import ORMModel


class EvaluateSubmissionRequest(BaseModel):
    provider_config_id: str | None = None
    provider_name: ProviderName | None = None


class BatchEvaluateRequest(BaseModel):
    submission_ids: list[str] = Field(min_length=1)


class BatchEvaluateResponse(BaseModel):
    queued_count: int
    already_running: bool = False


class BatchEvaluationStatusResponse(BaseModel):
    active: bool
    cancel_requested: bool = False
    total_count: int
    processed_count: int
    completed_count: int
    failed_count: int
    remaining_count: int
    current_submission_id: str | None = None
    queued_submission_ids: list[str] = Field(default_factory=list)
    completed_submission_ids: list[str] = Field(default_factory=list)
    failed_submission_ids: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class BatchEvaluateCancelResponse(BaseModel):
    cancel_requested: bool
    was_active: bool


class CriterionScoreResponse(ORMModel):
    id: str
    criterion_id: str
    criterion_name: str
    weight: float
    is_manual: bool
    ai_score: float | None
    manual_score: float | None
    feedback: str | None
    created_at: datetime
    updated_at: datetime


class EvaluationResultSummaryResponse(ORMModel):
    id: str
    submission_id: str
    submission_filename: str
    student_id: str | None = None
    group_id: str
    group_name: str
    grade_scale: int
    evaluation_number: int
    is_latest: bool
    provider_name: ProviderName | None = None
    model_name: str | None = None
    total_ai_score: float | None
    final_adjusted_score: float | None
    ai_feedback: str | None
    created_at: datetime
    provider_config_id: str | None = None


class EvaluationDetailResponse(EvaluationResultSummaryResponse):
    raw_ai_response: str | None
    criterion_scores: list[CriterionScoreResponse]


class ManualAdjustmentItem(BaseModel):
    criterion_score_id: str
    manual_score: float | None = Field(default=None, ge=0)
    feedback: str | None = Field(default=None, max_length=5000)


class ManualAdjustmentRequest(BaseModel):
    items: list[ManualAdjustmentItem]


class NormalizedCriterionEvaluation(BaseModel):
    criterion_name: str
    ai_score: float | None
    feedback: str | None


class NormalizedEvaluationResponse(BaseModel):
    total_score: float | None
    summary_feedback: str | None
    criterion_scores: list[NormalizedCriterionEvaluation]
    raw_response: str
    provider_name: ProviderName
    model_name: str
