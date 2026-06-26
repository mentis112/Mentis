from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_instructor
from app.db.session import get_db
from app.schemas.preferences import PreferenceResponse, PreferenceUpdateRequest
from app.services.preference_service import PreferenceService

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=PreferenceResponse)
async def get_preferences(
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    preference = await PreferenceService(db).get_for_instructor(current_instructor.id)
    return PreferenceResponse.model_validate(preference)


@router.patch("", response_model=PreferenceResponse)
async def update_preferences(
    payload: PreferenceUpdateRequest,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    preference = await PreferenceService(db).update_for_instructor(current_instructor.id, payload)
    return PreferenceResponse.model_validate(preference)

