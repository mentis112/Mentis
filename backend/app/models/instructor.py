from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ProviderName


class Instructor(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "instructors"

    username: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column("password", String(255), nullable=False)
    encrypted_api_key: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    api_provider: Mapped[ProviderName | None] = mapped_column(
        SAEnum(ProviderName, name="provider_name"),
        nullable=True,
    )

    assignment_groups = relationship("AssignmentGroup", back_populates="instructor")
    provider_configs = relationship("AIProviderConfig", back_populates="instructor")
    preferences = relationship("AppPreference", back_populates="instructor", uselist=False)
    audit_logs = relationship("AuditLog", back_populates="instructor")
    upload_batches = relationship("UploadBatch", back_populates="instructor")
    sessions = relationship("AuthSession", back_populates="instructor")


class AuthSession(UUIDMixin, Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (UniqueConstraint("refresh_token_hash", name="uq_auth_sessions_refresh_token_hash"),)

    instructor_id: Mapped[str] = mapped_column(ForeignKey("instructors.id", ondelete="CASCADE"))
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    instructor = relationship("Instructor", back_populates="sessions")
