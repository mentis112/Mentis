from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_instructor
from app.models.enums import ProviderName
from app.db.session import get_db
from app.schemas.providers import (
    ProviderConfigCreate,
    ProviderConfigResponse,
    ProviderConfigUpdate,
    ProviderConnectionTestResponse,
    ProviderUsageSummary,
)
from app.services.provider_service import ProviderService

router = APIRouter(prefix="/providers", tags=["providers"])


def _to_provider_response(model) -> ProviderConfigResponse:
    data = ProviderConfigResponse.model_validate(model).model_dump()
    data["has_api_key"] = model.provider_name != ProviderName.OLLAMA and bool(model.encrypted_api_key)
    return ProviderConfigResponse(**data)


@router.get("", response_model=list[ProviderConfigResponse])
async def list_providers(
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    providers = await ProviderService(db).list_configs(current_instructor.id)
    return [_to_provider_response(item) for item in providers]


@router.post("", response_model=ProviderConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: ProviderConfigCreate,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    provider = await ProviderService(db).create_config(current_instructor.id, payload)
    return _to_provider_response(provider)


@router.patch("/{provider_id}", response_model=ProviderConfigResponse)
async def update_provider(
    provider_id: str,
    payload: ProviderConfigUpdate,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    provider = await ProviderService(db).update_config(current_instructor.id, provider_id, payload)
    return _to_provider_response(provider)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: str,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    await ProviderService(db).delete_config(current_instructor.id, provider_id)


@router.post("/{provider_id}/test", response_model=ProviderConnectionTestResponse)
async def test_provider(
    provider_id: str,
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    success, message, provider = await ProviderService(db).test_connection(
        current_instructor.id,
        provider_id,
    )
    return ProviderConnectionTestResponse(
        success=success,
        message=message,
        provider_name=provider.provider_name,
        model_name=provider.model_name,
    )


@router.get("/usage", response_model=list[ProviderUsageSummary])
async def provider_usage(
    current_instructor=Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
):
    summary = await ProviderService(db).usage_summary(current_instructor.id)
    return [ProviderUsageSummary(**item) for item in summary]
