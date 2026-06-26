from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class AssignmentGroup(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "assignment_groups"

    instructor_id: Mapped[str] = mapped_column(ForeignKey("instructors.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    grade_scale: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    instructor = relationship("Instructor", back_populates="assignment_groups")
    criteria = relationship(
        "EvaluationCriterion",
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="EvaluationCriterion.sort_order",
    )
    submissions = relationship(
        "Submission",
        back_populates="group",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class EvaluationCriterion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_criteria"

    group_id: Mapped[str] = mapped_column(ForeignKey("assignment_groups.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    group = relationship("AssignmentGroup", back_populates="criteria")
    criterion_scores = relationship("CriterionScore", back_populates="criterion")
