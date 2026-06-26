from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.repositories.submission_repository import SubmissionRepository
from app.schemas.submissions import SubmissionStatusUpdateRequest, SubmissionStudentIdUpdateRequest
from app.services.audit_service import AuditService


class SubmissionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SubmissionRepository(session)
        self.audit_service = AuditService(session)

    async def list_submissions(
        self,
        instructor_id: str,
        *,
        group_id: str | None = None,
        missing_student_id_only: bool = False,
        page: int = 1,
        page_size: int = 25,
    ):
        return await self.repository.list_for_instructor(
            instructor_id,
            group_id=group_id,
            missing_student_id_only=missing_student_id_only,
            page=page,
            page_size=page_size,
        )

    async def list_submission_report(
        self,
        instructor_id: str,
        *,
        group_id: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ):
        return await self.repository.list_report_for_instructor(
            instructor_id,
            group_id=group_id,
            search=search,
            page=page,
            page_size=page_size,
        )

    async def list_evaluatable_submission_ids(self, instructor_id: str, group_id: str):
        return await self.repository.list_evaluatable_ids_for_group(instructor_id, group_id)

    async def get_submission(self, instructor_id: str, submission_id: str):
        submission = await self.repository.get_by_id_for_instructor(submission_id, instructor_id)
        if not submission:
            raise NotFoundError("Submission not found")
        return submission

    async def update_status(
        self, instructor_id: str, submission_id: str, payload: SubmissionStatusUpdateRequest
    ):
        submission = await self.get_submission(instructor_id, submission_id)
        submission.status = payload.status
        submission.error_message = payload.error_message
        await self.repository.save_submission(submission)
        await self.audit_service.log(
            instructor_id=instructor_id,
            action="submission.status_updated",
            entity_type="submission",
            entity_id=submission.id,
            metadata_json=payload.model_dump(),
        )
        await self.session.commit()
        return submission

    async def update_student_id(
        self, instructor_id: str, submission_id: str, payload: SubmissionStudentIdUpdateRequest
    ):
        submission = await self.get_submission(instructor_id, submission_id)
        previous_student_id = submission.student_id or None
        submission.student_id = payload.student_id.strip()
        await self.repository.save_submission(submission)
        await self.audit_service.log(
            instructor_id=instructor_id,
            action="submission.student_id_updated",
            entity_type="submission",
            entity_id=submission.id,
            metadata_json={
                "previous_student_id": previous_student_id,
                "student_id": submission.student_id,
            },
        )
        await self.session.commit()
        return submission
