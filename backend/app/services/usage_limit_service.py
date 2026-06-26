from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.models.enums import ProviderRequestType, ProviderUsageStatus
from app.models.provider import AIProviderConfig, ProviderUsageLog
from app.repositories.provider_repository import ProviderRepository


class UsageLimitService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ProviderRepository(session)

    async def enforce_evaluation_limits(
        self,
        *,
        instructor_id: str,
        provider_config: AIProviderConfig,
        estimated_tokens: int,
        files_count: int,
        file_size_mb: float,
    ) -> list[str]:
        warnings: list[str] = []
        day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        logs_today = await self.repository.list_usage_logs_since(instructor_id=instructor_id, since=day_start)
        logs_month = await self.repository.list_usage_logs_since(instructor_id=instructor_id, since=month_start)
        counted_request_types = {ProviderRequestType.EVALUATION, ProviderRequestType.RETRY}
        counted_statuses = {ProviderUsageStatus.SUCCESS, ProviderUsageStatus.FAILED}
        daily_count = sum(
            1
            for log in logs_today
            if log.provider_config_id == provider_config.id
            and log.request_type in counted_request_types
            and log.status in counted_statuses
        )
        monthly_count = sum(
            1
            for log in logs_month
            if log.provider_config_id == provider_config.id
            and log.request_type in counted_request_types
            and log.status in counted_statuses
        )

        if provider_config.daily_request_limit and daily_count >= provider_config.daily_request_limit:
            await self._log_block(instructor_id, provider_config, "Daily provider request limit exceeded")
            raise ValidationError("Daily provider request limit exceeded")
        if provider_config.monthly_request_limit and monthly_count >= provider_config.monthly_request_limit:
            await self._log_block(instructor_id, provider_config, "Monthly provider request limit exceeded")
            raise ValidationError("Monthly provider request limit exceeded")
        if provider_config.max_files_per_batch and files_count > provider_config.max_files_per_batch:
            raise ValidationError("Batch exceeds provider file count limit")
        if provider_config.max_file_size_mb and file_size_mb > provider_config.max_file_size_mb:
            raise ValidationError("File exceeds provider size limit")
        if provider_config.max_tokens_per_request and estimated_tokens > provider_config.max_tokens_per_request:
            await self._log_block(instructor_id, provider_config, "Prompt exceeds provider token limit")
            raise ValidationError("Prompt exceeds provider token limit")
        if provider_config.max_tokens_per_request and estimated_tokens > provider_config.max_tokens_per_request * 0.85:
            warnings.append("Prompt is close to the configured provider token limit.")
        return warnings

    async def _log_block(
        self,
        instructor_id: str,
        provider_config: AIProviderConfig,
        message: str,
    ) -> None:
        usage = ProviderUsageLog(
            instructor_id=instructor_id,
            provider_config_id=provider_config.id,
            provider_name=provider_config.provider_name,
            request_type=ProviderRequestType.EVALUATION,
            files_count=1,
            status=ProviderUsageStatus.BLOCKED_LIMIT,
            error_message=message,
        )
        await self.repository.create_usage_log(usage)
        await self.session.flush()
