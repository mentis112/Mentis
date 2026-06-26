from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import EvaluationDepth, ProviderName, ProviderRequestType, ProviderUsageStatus


class AIProviderConfig(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ai_provider_configs"

    instructor_id: Mapped[str] = mapped_column(ForeignKey("instructors.id", ondelete="CASCADE"), index=True)
    provider_name: Mapped[ProviderName] = mapped_column(
        SAEnum(ProviderName, name="provider_name"),
        index=True,
    )
    encrypted_api_key: Mapped[str] = mapped_column(String(2048), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)
    daily_request_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_request_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_files_per_batch: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_file_size_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_tokens_per_request: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evaluation_depth: Mapped[EvaluationDepth] = mapped_column(
        SAEnum(
            EvaluationDepth,
            name="evaluation_depth",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=EvaluationDepth.ACADEMIC_STANDARD,
        nullable=False,
    )

    instructor = relationship("Instructor", back_populates="provider_configs")
    usage_logs = relationship("ProviderUsageLog", back_populates="provider_config")


class ProviderUsageLog(UUIDMixin, Base):
    __tablename__ = "provider_usage_logs"

    instructor_id: Mapped[str] = mapped_column(ForeignKey("instructors.id", ondelete="CASCADE"), index=True)
    provider_config_id: Mapped[str | None] = mapped_column(
        ForeignKey("ai_provider_configs.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_name: Mapped[ProviderName] = mapped_column(
        SAEnum(ProviderName, name="provider_name"),
        index=True,
    )
    submission_id: Mapped[str | None] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"),
        nullable=True,
    )
    evaluation_result_id: Mapped[str | None] = mapped_column(
        ForeignKey("evaluation_results.id", ondelete="SET NULL"),
        nullable=True,
    )
    request_type: Mapped[ProviderRequestType] = mapped_column(
        SAEnum(ProviderRequestType, name="provider_request_type"),
        nullable=False,
    )
    tokens_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    files_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[ProviderUsageStatus] = mapped_column(
        SAEnum(ProviderUsageStatus, name="provider_usage_status"),
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    provider_config = relationship("AIProviderConfig", back_populates="usage_logs")
