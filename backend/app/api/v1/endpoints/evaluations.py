from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_instructor
from app.db.session import get_db
from app.models.evaluation import EvaluationResult
from app.schemas.evaluations import (
    BatchEvaluateRequest,
    BatchEvaluateCancelResponse,
    BatchEvaluateResponse,
    BatchEvaluationStatusResponse,
    CriterionScoreResponse,
    EvaluateSubmissionRequest,
    EvaluationDetailResponse,
    EvaluationResultSummaryResponse,
    ManualAdjustmentRequest,
)
from app.services.evaluation_batch_runner import EvaluationBatchRunner
from app.services.evaluation_service import EvaluationService

router = APIRouter(tags=["evaluations"])


def _to_evaluation_summary(model: EvaluationResult) -> EvaluationResultSummaryResponse:
    return EvaluationResultSummaryResponse(
        id=model.id,
        submission_id=model.submission_id,
        submission_filename=model.submission.original_filename,
        student_id=model.submission.student_id,
        group_id=model.submission.group.id,
        group_name=model.submission.group.name,
        grade_scale=model.submission.group.grade_scale,
        evaluation_number=model.evaluation_number,
        is_latest=model.is_latest,
        provider_name=model.provider_name,
        model_name=model.model_name,
        total_ai_score=float(model.total_ai_score) if model.total_ai_score is not None else None,
        final_adjusted_score=(
            float(model.final_adjusted_score) if model.final_adjusted_score is not None else None
        ),
        ai_feedback=model.ai_feedback,
        created_at=model.created_at,
        provider_config_id=model.provider_config_id,
    )


def _to_evaluation_detail(model: EvaluationResult) -> EvaluationDetailResponse:
    return EvaluationDetailResponse(
        **_to_evaluation_summary(model).model_dump(),
        raw_ai_response=model.raw_ai_response,
        criterion_scores=[
            CriterionScoreResponse(
                id=score.id,
                criterion_id=score.criterion_id,
                criterion_name=score.criterion.name,
                weight=float(score.criterion.weight),
                is_manual=score.criterion.is_manual,
                ai_score=float(score.ai_score) if score.ai_score is not None else None,
                manual_score=float(score.manual_score) if score.manual_score is not None else None,
                feedback=score.feedback,
                created_at=score.created_at,
                updated_at=score.updated_at,
            )
            for score in model.criterion_scores
        ],
    )


@router.post(
    "/submissions/{submission_id}/evaluate",
    response_model=EvaluationDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def evaluate_submission(
    submission_id: str,
    payload: EvaluateSubmissionRequest,
    accept_language: str | None = Header(default=None),
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    service = EvaluationService(db)
    evaluation = await service.evaluate_submission(
        instructor_id=current_instructor.id,
        submission_id=submission_id,
        payload=payload,
        response_language=service.normalize_response_language(accept_language),
    )
    return _to_evaluation_detail(evaluation)


@router.post(
    "/submissions/{submission_id}/re-evaluate",
    response_model=EvaluationDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def re_evaluate_submission(
    submission_id: str,
    payload: EvaluateSubmissionRequest,
    accept_language: str | None = Header(default=None),
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    service = EvaluationService(db)
    evaluation = await service.evaluate_submission(
        instructor_id=current_instructor.id,
        submission_id=submission_id,
        payload=payload,
        response_language=service.normalize_response_language(accept_language),
    )
    return _to_evaluation_detail(evaluation)


@router.post("/evaluations/batch/start", response_model=BatchEvaluateResponse)
async def start_batch_evaluations(
    payload: BatchEvaluateRequest,
    accept_language: str | None = Header(default=None),
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    service = EvaluationService(db)
    queued_count, already_running = await service.start_batch_evaluations(
        instructor_id=current_instructor.id,
        submission_ids=payload.submission_ids,
        response_language=service.normalize_response_language(accept_language),
    )
    return BatchEvaluateResponse(
        queued_count=queued_count,
        already_running=already_running,
    )


@router.get("/evaluations/batch/status", response_model=BatchEvaluationStatusResponse)
async def get_batch_evaluation_status(current_instructor=Depends(get_current_instructor)):
    return BatchEvaluationStatusResponse(**EvaluationBatchRunner.get_status(current_instructor.id))


@router.post("/evaluations/batch/cancel", response_model=BatchEvaluateCancelResponse)
async def cancel_batch_evaluations(current_instructor=Depends(get_current_instructor)):
    was_active = EvaluationBatchRunner.is_active(current_instructor.id)
    cancel_requested = EvaluationBatchRunner.request_cancel(current_instructor.id)
    return BatchEvaluateCancelResponse(
        cancel_requested=cancel_requested,
        was_active=was_active,
    )


@router.get("/submissions/{submission_id}/evaluations", response_model=list[EvaluationResultSummaryResponse])
async def list_submission_evaluations(
    submission_id: str,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    evaluations = await EvaluationService(db).list_for_submission(current_instructor.id, submission_id)
    return [_to_evaluation_summary(item) for item in evaluations]


@router.get("/evaluations", response_model=list[EvaluationResultSummaryResponse])
async def list_all_evaluations(
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    evaluations = await EvaluationService(db).list_for_instructor(current_instructor.id)
    return [_to_evaluation_summary(item) for item in evaluations]


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationDetailResponse)
async def get_evaluation(
    evaluation_id: str,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    evaluation = await EvaluationService(db).get_by_id(current_instructor.id, evaluation_id)
    return _to_evaluation_detail(evaluation)


@router.patch("/evaluations/{evaluation_id}/manual-adjustments", response_model=EvaluationDetailResponse)
async def apply_manual_adjustments(
    evaluation_id: str,
    payload: ManualAdjustmentRequest,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    evaluation = await EvaluationService(db).apply_manual_adjustments(
        instructor_id=current_instructor.id,
        evaluation_id=evaluation_id,
        payload=payload,
    )
    return _to_evaluation_detail(evaluation)
