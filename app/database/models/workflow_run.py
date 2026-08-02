from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.database.base import Base


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (CheckConstraint("state_version >= 1", name="state_version_positive"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    thread_id: Mapped[str] = mapped_column(String(64), unique=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    scenario_type: Mapped[str] = mapped_column(String(30))
    repository_path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50))
    current_stage: Mapped[str] = mapped_column(String(80))
    state_version: Mapped[int] = mapped_column(Integer, default=1)
    original_branch: Mapped[str | None] = mapped_column(String(255))
    baseline_commit: Mapped[str | None] = mapped_column(String(64))
    working_branch: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    requirements: Mapped[list[WorkflowRequirement]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )
    tasks: Mapped[list[WorkflowTask]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )
    approval_requests: Mapped[list[ApprovalRequest]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )
    agent_executions: Mapped[list[AgentExecution]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list[WorkflowArtifact]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="workflow")


from app.database.models.agent_execution import AgentExecution  # noqa: E402
from app.database.models.approval_request import ApprovalRequest  # noqa: E402
from app.database.models.audit_event import AuditEvent  # noqa: E402
from app.database.models.workflow_artifact import WorkflowArtifact  # noqa: E402
from app.database.models.workflow_requirement import WorkflowRequirement  # noqa: E402
from app.database.models.workflow_task import WorkflowTask  # noqa: E402
