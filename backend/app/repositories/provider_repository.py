from datetime import datetime

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProviderName
from app.models.provider import AIProviderConfig, ProviderUsageLog


class ProviderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_instructor(self, instructor_id: str) -> list[AIProviderConfig]:
        result = await self.session.execute(
            select(AIProviderConfig)
            .where(AIProviderConfig.instructor_id == instructor_id)
            .order_by(AIProviderConfig.provider_name, AIProviderConfig.created_at)
        )
        return list(result.scalars().all())

    async def get_by_id_for_instructor(
        self, provider_config_id: str, instructor_id: str
    ) -> AIProviderConfig | None:
        result = await self.session.execute(
            select(AIProviderConfig).where(
                AIProviderConfig.id == provider_config_id,
                AIProviderConfig.instructor_id == instructor_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_default_for_instructor(self, instructor_id: str) -> AIProviderConfig | None:
        result = await self.session.execute(
            select(AIProviderConfig).where(
                AIProviderConfig.instructor_id == instructor_id,
                AIProviderConfig.is_default.is_(True),
                AIProviderConfig.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_provider_name(
        self, instructor_id: str, provider_name: ProviderName
    ) -> AIProviderConfig | None:
        result = await self.session.execute(
            select(AIProviderConfig).where(
                AIProviderConfig.instructor_id == instructor_id,
                AIProviderConfig.provider_name == provider_name,
                AIProviderConfig.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def clear_defaults(self, instructor_id: str) -> None:
        await self.session.execute(
            update(AIProviderConfig)
            .where(AIProviderConfig.instructor_id == instructor_id)
            .values(is_default=False)
        )

    async def create(self, provider_config: AIProviderConfig) -> AIProviderConfig:
        self.session.add(provider_config)
        await self.session.flush()
        return provider_config

    async def save(self, provider_config: AIProviderConfig) -> AIProviderConfig:
        self.session.add(provider_config)
        await self.session.flush()
        return provider_config

    async def delete(self, provider_config: AIProviderConfig) -> None:
        await self.session.delete(provider_config)
        await self.session.flush()

    async def get_fallback_default_candidate(self, instructor_id: str) -> AIProviderConfig | None:
        result = await self.session.execute(
            select(AIProviderConfig)
            .where(
                AIProviderConfig.instructor_id == instructor_id,
                AIProviderConfig.is_active.is_(True),
            )
            .order_by(desc(AIProviderConfig.updated_at), desc(AIProviderConfig.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_usage_log(self, usage_log: ProviderUsageLog) -> ProviderUsageLog:
        self.session.add(usage_log)
        await self.session.flush()
        return usage_log

    async def list_usage_logs_since(
        self,
        *,
        instructor_id: str,
        since: datetime,
    ) -> list[ProviderUsageLog]:
        result = await self.session.execute(
            select(ProviderUsageLog)
            .where(
                ProviderUsageLog.instructor_id == instructor_id,
                ProviderUsageLog.created_at >= since,
            )
            .order_by(desc(ProviderUsageLog.created_at))
        )
        return list(result.scalars().all())
