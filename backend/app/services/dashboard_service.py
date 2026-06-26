from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.dashboard_repository import DashboardRepository


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = DashboardRepository(session)

    async def summary(self, instructor_id: str) -> dict:
        return await self.repository.summary(instructor_id)
