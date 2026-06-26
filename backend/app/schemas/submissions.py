from datetime import datetime
import re

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ParserStatus, SubmissionStatus, UploadBatchStatus
from app.schemas.common import ListResponse
from app.schemas.evaluations import EvaluationDetailResponse
from app.schemas.common import ORMModel


class SubmissionStatusUpdateRequest(BaseModel):
    status: SubmissionStatus
    error_message: str | None = Field(default=None, max_length=4000)


class SubmissionStudentIdUpdateRequest(BaseModel):
    student_id: str = Field(..., min_length=1, max_length=100)

    @field_validator("student_id")
    @classmethod
    def strip_student_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Student ID is required")
        if not re.fullmatch(r"\d{5,}", cleaned):
            raise ValueError("Student ID must contain digits only and be at least 5 digits long")
        return cleaned


class SubmissionResponse(ORMModel):
    id: str
    group_id: str
    upload_batch_id: str | None
    file_path: str
    original_filename: str
    student_id: str
    status: SubmissionStatus
    error_message: str | None
    created_at: datetime
    processed_at: datetime | None


class SubmissionContentCacheResponse(ORMModel):
    extracted_text: str | None
    parser_status: ParserStatus
    parser_error: str | None


class UploadBatchResponse(ORMModel):
    id: str
    instructor_id: str
    group_id: str
    total_files: int
    accepted_files: int
    rejected_files: int
    status: UploadBatchStatus
    created_at: datetime


class UploadedFileResult(BaseModel):
    original_filename: str
    source_upload_index: int | None = None
    source_upload_filename: str | None = None
    from_archive: bool = False
    student_id: str | None = None
    accepted: bool
    reason: str | None = None
    submission_id: str | None = None
    status: SubmissionStatus | None = None
    needs_student_id: bool = False
    is_duplicate: bool = False
    duplicate_reasons: list[str] = Field(default_factory=list)
    has_existing_match: bool = False
    existing_duplicate_reasons: list[str] = Field(default_factory=list)
    existing_submission_id: str | None = None
    existing_submission_evaluated: bool = False


class StudentIdPreviewResult(BaseModel):
    original_filename: str
    source_upload_index: int | None = None
    source_upload_filename: str | None = None
    from_archive: bool = False
    student_id: str | None = None
    accepted: bool
    reason: str | None = None
    needs_student_id: bool = False
    is_duplicate: bool = False
    duplicate_reasons: list[str] = Field(default_factory=list)
    has_existing_match: bool = False
    existing_duplicate_reasons: list[str] = Field(default_factory=list)
    existing_submission_id: str | None = None
    existing_submission_evaluated: bool = False


class SubmissionUploadResponse(BaseModel):
    batch: UploadBatchResponse
    results: list[UploadedFileResult]


class SubmissionStudentIdPreviewResponse(BaseModel):
    results: list[StudentIdPreviewResult]


class SubmissionReportRowResponse(BaseModel):
    submission: SubmissionResponse
    grade_scale: int
    latest_evaluation: EvaluationDetailResponse | None = None


class SubmissionListResponse(ListResponse[SubmissionResponse]):
    pass


class SubmissionReportListResponse(ListResponse[SubmissionReportRowResponse]):
    pass


class SubmissionIdListResponse(BaseModel):
    items: list[str]
