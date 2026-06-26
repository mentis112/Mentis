from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AppLanguage, ThemeMode
from app.models.preferences import AppPreference


class PreferenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_instructor_id(self, instructor_id: str) -> AppPreference | None:
        result = await self.session.execute(
            select(AppPreference).where(AppPreference.instructor_id == instructor_id)
        )
        return result.scalar_one_or_none()

    async def create_default(self, instructor_id: str) -> AppPreference:
        preference = AppPreference(
            instructor_id=instructor_id,
            language=AppLanguage.EN,
            theme=ThemeMode.SYSTEM,
        )
        self.session.add(preference)
        await self.session.flush()
        return preference

    async def save(self, preference: AppPreference) -> AppPreference:
        self.session.add(preference)
        await self.session.flush()
        return preference

