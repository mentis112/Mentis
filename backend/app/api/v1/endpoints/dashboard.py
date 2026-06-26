from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_instructor
from app.db.session import get_db
from app.schemas.dashboard import DashboardSummaryResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
async def dashboard_summary(
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    summary = await DashboardService(db).summary(current_instructor.id)
    return DashboardSummaryResponse(**summary)

