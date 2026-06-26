from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ProviderName


class EvaluationResult(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_results"

    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    provider_config_id: Mapped[str | None] = mapped_column(
        ForeignKey("ai_provider_configs.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_name: Mapped[ProviderName | None] = mapped_column(
        SAEnum(ProviderName, name="provider_name"),
        nullable=True,
    )
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    evaluation_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    total_ai_score: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    final_adjusted_score: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_ai_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    submission = relationship("Submission", back_populates="evaluations")
    criterion_scores = relationship(
        "CriterionScore",
        back_populates="result",
        cascade="all, delete-orphan",
    )


class CriterionScore(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "criterion_scores"

    result_id: Mapped[str] = mapped_column(ForeignKey("evaluation_results.id", ondelete="CASCADE"), index=True)
    criterion_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_criteria.id", ondelete="CASCADE"),
        index=True,
    )
    ai_score: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    manual_score: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    result = relationship("EvaluationResult", back_populates="criterion_scores")
    criterion = relationship("EvaluationCriterion", back_populates="criterion_scores")
    adjustment_history = relationship(
        "ManualAdjustmentHistory",
        back_populates="criterion_score",
        cascade="all, delete-orphan",
    )


class ManualAdjustmentHistory(UUIDMixin, Base):
    __tablename__ = "manual_adjustment_history"

    criterion_score_id: Mapped[str] = mapped_column(
        ForeignKey("criterion_scores.id", ondelete="CASCADE"),
        index=True,
    )
    instructor_id: Mapped[str] = mapped_column(ForeignKey("instructors.id", ondelete="CASCADE"), index=True)
    previous_manual_score: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    new_manual_score: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    previous_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    criterion_score = relationship("CriterionScore", back_populates="adjustment_history")
