from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.ai.factory import ProviderAdapterFactory
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import decrypt_secret, encrypt_secret
from app.models.enums import EvaluationDepth, ProviderRequestType, ProviderUsageStatus
from app.models.provider import AIProviderConfig, ProviderUsageLog
from app.repositories.provider_repository import ProviderRepository
from app.schemas.providers import ProviderConfigCreate, ProviderConfigUpdate
from app.services.audit_service import AuditService


class ProviderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ProviderRepository(session)
        self.audit_service = AuditService(session)

    async def list_configs(self, instructor_id: str) -> list[AIProviderConfig]:
        return await self.repository.list_for_instructor(instructor_id)

    async def create_config(self, instructor_id: str, payload: ProviderConfigCreate) -> AIProviderConfig:
        adapter = ProviderAdapterFactory.create(payload.provider_name)
        adapter.validate_provider_config(api_key=payload.api_key, model_name=payload.model_name)

        existing = await self.repository.list_for_instructor(instructor_id)
        is_default = payload.is_default or not existing
        if is_default:
            await self.repository.clear_defaults(instructor_id)

        provider_config = AIProviderConfig(
            instructor_id=instructor_id,
            provider_name=payload.provider_name,
            encrypted_api_key=encrypt_secret(payload.api_key),
            model_name=payload.model_name,
            is_active=payload.is_active,
            is_default=is_default,
            daily_request_limit=payload.daily_request_limit,
            monthly_request_limit=payload.monthly_request_limit,
            max_files_per_batch=payload.max_files_per_batch,
            max_file_size_mb=payload.max_file_size_mb,
            max_tokens_per_request=payload.max_tokens_per_request,
            evaluation_depth=EvaluationDepth.ACADEMIC_STANDARD,
        )
        await self.repository.create(provider_config)
        await self.audit_service.log(
            instructor_id=instructor_id,
            action="provider.created",
            entity_type="ai_provider_config",
            entity_id=provider_config.id,
            metadata_json={"provider_name": payload.provider_name.value, "model_name": payload.model_name},
        )
        await self.session.commit()
        return provider_config

    async def update_config(
        self, instructor_id: str, provider_config_id: str, payload: ProviderConfigUpdate
    ) -> AIProviderConfig:
        provider_config = await self.repository.get_by_id_for_instructor(provider_config_id, instructor_id)
        if not provider_config:
            raise NotFoundError("Provider configuration not found")

        updates = payload.model_dump(exclude_unset=True)
        api_key = updates.pop("api_key", None)
        if api_key is not None:
            provider_config.encrypted_api_key = encrypt_secret(api_key)
        for field, value in updates.items():
            setattr(provider_config, field, value)
        if provider_config.is_default:
            await self.repository.clear_defaults(instructor_id)
            provider_config.is_default = True

        adapter = ProviderAdapterFactory.create(provider_config.provider_name)
        adapter.validate_provider_config(
            api_key=api_key or decrypt_secret(provider_config.encrypted_api_key),
            model_name=provider_config.model_name,
        )
        await self.repository.save(provider_config)
        await self.audit_service.log(
            instructor_id=instructor_id,
            action="provider.updated",
            entity_type="ai_provider_config",
            entity_id=provider_config.id,
            metadata_json={"provider_name": provider_config.provider_name.value},
        )
        await self.session.commit()
        return provider_config

    async def test_connection(self, instructor_id: str, provider_config_id: str) -> tuple[bool, str, AIProviderConfig]:
        provider_config = await self.repository.get_by_id_for_instructor(provider_config_id, instructor_id)
        if not provider_config:
            raise NotFoundError("Provider configuration not found")
        adapter = ProviderAdapterFactory.create(provider_config.provider_name)
        success = False
        message = ""
        try:
            success, message = await adapter.test_connection(
                api_key=decrypt_secret(provider_config.encrypted_api_key),
                model_name=provider_config.model_name,
            )
            status = ProviderUsageStatus.SUCCESS
        except Exception as exc:
            message = str(exc)
            status = ProviderUsageStatus.FAILED
        usage = ProviderUsageLog(
            instructor_id=instructor_id,
            provider_config_id=provider_config.id,
            provider_name=provider_config.provider_name,
            request_type=ProviderRequestType.TEST_CONNECTION,
            files_count=0,
            status=status,
            error_message=None if success else message,
            created_at=datetime.now(timezone.utc),
        )
        await self.repository.create_usage_log(usage)
        await self.audit_service.log(
            instructor_id=instructor_id,
            action="provider.test_connection",
            entity_type="ai_provider_config",
            entity_id=provider_config.id,
            metadata_json={"success": success, "message": message},
        )
        await self.session.commit()
        return success, message, provider_config

    async def delete_config(self, instructor_id: str, provider_config_id: str) -> None:
        provider_config = await self.repository.get_by_id_for_instructor(provider_config_id, instructor_id)
        if not provider_config:
            raise NotFoundError("Provider configuration not found")

        was_default = provider_config.is_default
        deleted_id = provider_config.id
        provider_name = provider_config.provider_name.value
        await self.repository.delete(provider_config)

        if was_default:
            fallback = await self.repository.get_fallback_default_candidate(instructor_id)
            if fallback:
                await self.repository.clear_defaults(instructor_id)
                fallback.is_default = True
                await self.repository.save(fallback)

        await self.audit_service.log(
            instructor_id=instructor_id,
            action="provider.deleted",
            entity_type="ai_provider_config",
            entity_id=deleted_id,
            metadata_json={"provider_name": provider_name},
        )
        await self.session.commit()

    async def resolve_config(
        self,
        instructor_id: str,
        *,
        provider_config_id: str | None = None,
        provider_name=None,
    ) -> AIProviderConfig:
        provider_config = None
        if provider_config_id:
            provider_config = await self.repository.get_by_id_for_instructor(provider_config_id, instructor_id)
        elif provider_name:
            provider_config = await self.repository.get_active_by_provider_name(instructor_id, provider_name)
        else:
            provider_config = await self.repository.get_default_for_instructor(instructor_id)
        if not provider_config or not provider_config.is_active:
            raise ValidationError("No active AI provider configuration is available")
        return provider_config

    async def usage_summary(self, instructor_id: str) -> list[dict]:
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        logs = await self.repository.list_usage_logs_since(instructor_id=instructor_id, since=month_start)
        summary: dict[str, dict] = {}
        for log in logs:
            bucket = summary.setdefault(
                log.provider_name.value,
                {
                    "provider_name": log.provider_name,
                    "requests_today": 0,
                    "requests_this_month": 0,
                    "failures_this_month": 0,
                    "blocked_this_month": 0,
                    "tokens_input_this_month": 0,
                    "tokens_output_this_month": 0,
                },
            )
            bucket["requests_this_month"] += 1
            if log.created_at >= day_start:
                bucket["requests_today"] += 1
            if log.status == ProviderUsageStatus.FAILED:
                bucket["failures_this_month"] += 1
            if log.status == ProviderUsageStatus.BLOCKED_LIMIT:
                bucket["blocked_this_month"] += 1
            bucket["tokens_input_this_month"] += log.tokens_input or 0
            bucket["tokens_output_this_month"] += log.tokens_output or 0
        return list(summary.values())
