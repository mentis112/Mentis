from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.repositories.preference_repository import PreferenceRepository
from app.schemas.preferences import PreferenceUpdateRequest
from app.services.audit_service import AuditService


class PreferenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = PreferenceRepository(session)
        self.audit_service = AuditService(session)

    async def get_for_instructor(self, instructor_id: str):
        preference = await self.repository.get_by_instructor_id(instructor_id)
        if not preference:
            raise NotFoundError("Preferences not found")
        return preference

    async def update_for_instructor(self, instructor_id: str, payload: PreferenceUpdateRequest):
        preference = await self.get_for_instructor(instructor_id)
        preference.language = payload.language
        preference.theme = payload.theme
        await self.repository.save(preference)
        await self.audit_service.log(
            instructor_id=instructor_id,
            action="preferences.updated",
            entity_type="app_preference",
            entity_id=preference.id,
            metadata_json=payload.model_dump(),
        )
        await self.session.commit()
        return preference

