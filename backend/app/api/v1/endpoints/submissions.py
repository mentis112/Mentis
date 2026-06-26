import json

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_instructor
from app.core.exceptions import ValidationError
from app.db.session import get_db
from app.schemas.submissions import (
    StudentIdPreviewResult,
    SubmissionIdListResponse,
    SubmissionListResponse,
    SubmissionReportListResponse,
    SubmissionReportRowResponse,
    SubmissionResponse,
    SubmissionStudentIdPreviewResponse,
    SubmissionStatusUpdateRequest,
    SubmissionStudentIdUpdateRequest,
    SubmissionUploadResponse,
    UploadBatchResponse,
    UploadedFileResult,
)
from app.services.submission_service import SubmissionService
from app.services.upload_service import UploadService
from app.api.v1.endpoints.evaluations import _to_evaluation_detail

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.get("", response_model=SubmissionListResponse)
async def list_submissions(
    group_id: str | None = Query(default=None),
    missing_student_id_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=500),
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    submissions, total = await SubmissionService(db).list_submissions(
        current_instructor.id,
        group_id=group_id,
        missing_student_id_only=missing_student_id_only,
        page=page,
        page_size=page_size,
    )
    return SubmissionListResponse(
        items=[SubmissionResponse.model_validate(item) for item in submissions],
        total=total,
    )


@router.get("/report", response_model=SubmissionReportListResponse)
async def submission_report(
    group_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=500),
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    submissions, total = await SubmissionService(db).list_submission_report(
        current_instructor.id,
        group_id=group_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    rows: list[SubmissionReportRowResponse] = []
    for submission in submissions:
        latest_evaluation = next((item for item in submission.evaluations if item.is_latest), None)
        rows.append(
            SubmissionReportRowResponse(
                submission=SubmissionResponse.model_validate(submission),
                grade_scale=submission.group.grade_scale,
                latest_evaluation=_to_evaluation_detail(latest_evaluation) if latest_evaluation else None,
            )
        )
    return SubmissionReportListResponse(items=rows, total=total)


@router.get("/evaluatable-ids", response_model=SubmissionIdListResponse)
async def list_evaluatable_submission_ids(
    group_id: str = Query(...),
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    submission_ids = await SubmissionService(db).list_evaluatable_submission_ids(
        current_instructor.id,
        group_id,
    )
    return SubmissionIdListResponse(items=submission_ids)


@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: str,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    submission = await SubmissionService(db).get_submission(current_instructor.id, submission_id)
    return SubmissionResponse.model_validate(submission)


@router.post("/upload", response_model=SubmissionUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_submissions(
    group_id: str = Form(...),
    student_ids: list[str] | None = Form(None),
    student_id_overrides_json: str | None = Form(None),
    excluded_archive_entries: list[str] | None = Form(None),
    allowed_existing_duplicates: list[str] | None = Form(None),
    files: list[UploadFile] = File(...),
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    student_id_overrides: dict[str, str] = {}
    if student_id_overrides_json:
        try:
            parsed = json.loads(student_id_overrides_json)
        except json.JSONDecodeError as exc:
            raise ValidationError("Invalid student ID overrides payload") from exc
        if not isinstance(parsed, dict):
            raise ValidationError("Student ID overrides must be a JSON object")
        student_id_overrides = {
            str(key): str(value)
            for key, value in parsed.items()
            if str(value).strip()
        }

    batch, results = await UploadService(db).upload_files(
        instructor_id=current_instructor.id,
        group_id=group_id,
        student_ids=student_ids or [],
        student_id_overrides=student_id_overrides,
        files=files,
        excluded_archive_entries=excluded_archive_entries or [],
        allowed_existing_duplicates=allowed_existing_duplicates or [],
    )
    return SubmissionUploadResponse(
        batch=UploadBatchResponse.model_validate(batch),
        results=[UploadedFileResult(**item) for item in results],
    )


@router.post("/preview-student-ids", response_model=SubmissionStudentIdPreviewResponse)
async def preview_submission_student_ids(
    group_id: str | None = Form(None),
    excluded_archive_entries: list[str] | None = Form(None),
    files: list[UploadFile] = File(...),
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    results = await UploadService(db).preview_student_ids(
        instructor_id=current_instructor.id,
        group_id=group_id,
        files=files,
        excluded_archive_entries=excluded_archive_entries or [],
    )
    return SubmissionStudentIdPreviewResponse(results=[StudentIdPreviewResult(**item) for item in results])


@router.patch("/{submission_id}/status", response_model=SubmissionResponse)
async def update_submission_status(
    submission_id: str,
    payload: SubmissionStatusUpdateRequest,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    submission = await SubmissionService(db).update_status(current_instructor.id, submission_id, payload)
    return SubmissionResponse.model_validate(submission)


@router.patch("/{submission_id}/student-id", response_model=SubmissionResponse)
async def update_submission_student_id(
    submission_id: str,
    payload: SubmissionStudentIdUpdateRequest,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    submission = await SubmissionService(db).update_student_id(current_instructor.id, submission_id, payload)
    return SubmissionResponse.model_validate(submission)
