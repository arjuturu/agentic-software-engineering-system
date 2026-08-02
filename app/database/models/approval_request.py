from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.database.base import Base


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (Index("ix_approval_requests_workflow_id_status", "workflow_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"))
    gate_type: Mapped[str] = mapped_column(String(50))
    state_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    allowed_actions_json: Mapped[list[object]] = mapped_column(MutableList.as_mutable(JSON))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    workflow: Mapped[WorkflowRun] = relationship(back_populates="approval_requests")
    decision: Mapped[ApprovalDecision | None] = relationship(
        back_populates="approval_request", cascade="all, delete-orphan", uselist=False
    )


from app.database.models.approval_decision import ApprovalDecision  # noqa: E402
from app.database.models.workflow_run import WorkflowRun  # noqa: E402
