from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ParserStatus, SubmissionStatus, UploadBatchStatus


class UploadBatch(UUIDMixin, Base):
    __tablename__ = "upload_batches"

    instructor_id: Mapped[str] = mapped_column(ForeignKey("instructors.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("assignment_groups.id", ondelete="CASCADE"), index=True)
    total_files: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[UploadBatchStatus] = mapped_column(
        SAEnum(UploadBatchStatus, name="upload_batch_status"),
        default=UploadBatchStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    instructor = relationship("Instructor", back_populates="upload_batches")
    submissions = relationship("Submission", back_populates="upload_batch")


class Submission(UUIDMixin, Base):
    __tablename__ = "submissions"

    group_id: Mapped[str] = mapped_column(ForeignKey("assignment_groups.id", ondelete="CASCADE"), index=True)
    upload_batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    student_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[SubmissionStatus] = mapped_column(
        SAEnum(SubmissionStatus, name="submission_status"),
        default=SubmissionStatus.PENDING,
        nullable=False,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    group = relationship("AssignmentGroup", back_populates="submissions")
    upload_batch = relationship("UploadBatch", back_populates="submissions")
    evaluations = relationship(
        "EvaluationResult",
        back_populates="submission",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    content_cache = relationship(
        "SubmissionContentCache",
        back_populates="submission",
        uselist=False,
        cascade="all, delete-orphan",
    )


class SubmissionContentCache(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "submission_content_cache"

    submission_id: Mapped[str] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser_status: Mapped[ParserStatus] = mapped_column(
        SAEnum(ParserStatus, name="parser_status"),
        default=ParserStatus.NOT_STARTED,
        nullable=False,
    )
    parser_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    submission = relationship("Submission", back_populates="content_cache")
