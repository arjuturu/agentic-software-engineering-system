from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.database.base import Base


class AgentExecution(Base):
    __tablename__ = "agent_executions"
    __table_args__ = (
        CheckConstraint("attempt_number >= 1", name="attempt_number_positive"),
        Index("ix_agent_executions_workflow_id_agent_name", "workflow_id", "agent_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"))
    agent_name: Mapped[str] = mapped_column(String(100))
    stage: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(40))
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    input_artifact: Mapped[str | None] = mapped_column(Text)
    output_artifact: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    workflow: Mapped[WorkflowRun] = relationship(back_populates="agent_executions")


from app.database.models.workflow_run import WorkflowRun  # noqa: E402
