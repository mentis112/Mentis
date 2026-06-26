from fastapi import APIRouter

from app.schemas.common import MessageResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=MessageResponse)
async def healthcheck():
    return MessageResponse(message="ok")

