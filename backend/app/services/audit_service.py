from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit_repository import AuditRepository


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = AuditRepository(session)

    async def log(
        self,
        *,
        instructor_id: str | None,
        action: str,
        entity_type: str,
        entity_id: str,
        metadata_json: dict | None = None,
    ):
        return await self.repository.create(
            instructor_id=instructor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata_json,
        )

    async def list_for_instructor(self, instructor_id: str, limit: int = 100):
        return await self.repository.list_for_instructor(instructor_id, limit)

