from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.preferences import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        instructor_id: str | None,
        action: str,
        entity_type: str,
        entity_id: str,
        metadata_json: dict | None = None,
    ) -> AuditLog:
        audit_log = AuditLog(
            instructor_id=instructor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata_json,
        )
        self.session.add(audit_log)
        await self.session.flush()
        return audit_log

    async def list_for_instructor(self, instructor_id: str, limit: int = 100) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.instructor_id == instructor_id)
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

