from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import AppLanguage, ThemeMode


class AppPreference(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "app_preferences"

    instructor_id: Mapped[str] = mapped_column(
        ForeignKey("instructors.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    language: Mapped[AppLanguage] = mapped_column(
        SAEnum(AppLanguage, name="app_language"),
        default=AppLanguage.EN,
        nullable=False,
    )
    theme: Mapped[ThemeMode] = mapped_column(
        SAEnum(ThemeMode, name="theme_mode"),
        default=ThemeMode.SYSTEM,
        nullable=False,
    )

    instructor = relationship("Instructor", back_populates="preferences")


class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_logs"

    instructor_id: Mapped[str | None] = mapped_column(
        ForeignKey("instructors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    instructor = relationship("Instructor", back_populates="audit_logs")
