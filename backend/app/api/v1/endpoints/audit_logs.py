from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_instructor
from app.db.session import get_db
from app.schemas.audit import AuditLogResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_logs(
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    logs = await AuditService(db).list_for_instructor(current_instructor.id)
    return [AuditLogResponse.model_validate(item) for item in logs]

