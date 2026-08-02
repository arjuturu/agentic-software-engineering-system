from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.database.base import Base


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"
    __table_args__ = (UniqueConstraint("approval_id", name="uq_approval_decisions_approval_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    approval_id: Mapped[str] = mapped_column(ForeignKey("approval_requests.id"))
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"))
    action: Mapped[str] = mapped_column(String(40))
    comments: Mapped[str | None] = mapped_column(Text)
    conditions_json: Mapped[list[object]] = mapped_column(
        MutableList.as_mutable(JSON), default=list
    )
    decided_by: Mapped[str] = mapped_column(String(255))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    approval_request: Mapped[ApprovalRequest] = relationship(back_populates="decision")


from app.database.models.approval_request import ApprovalRequest  # noqa: E402
