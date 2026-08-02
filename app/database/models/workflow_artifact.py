from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.database.base import Base


class WorkflowArtifact(Base):
    __tablename__ = "workflow_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "artifact_type",
            "version",
            name="uq_workflow_artifacts_workflow_type_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"))
    artifact_type: Mapped[str] = mapped_column(String(80))
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    workflow: Mapped[WorkflowRun] = relationship(back_populates="artifacts")


from app.database.models.workflow_run import WorkflowRun  # noqa: E402
