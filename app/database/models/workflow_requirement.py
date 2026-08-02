from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.database.base import Base


class WorkflowRequirement(Base):
    __tablename__ = "workflow_requirements"
    __table_args__ = (
        UniqueConstraint(
            "workflow_id", "version", name="uq_workflow_requirements_workflow_version"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"))
    version: Mapped[int] = mapped_column(Integer)
    original_requirement: Mapped[str] = mapped_column(Text)
    normalized_requirement: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40))
    analysis_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    workflow: Mapped[WorkflowRun] = relationship(back_populates="requirements")


from app.database.models.workflow_run import WorkflowRun  # noqa: E402

