from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.database.base import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_workflow_id_occurred_at", "workflow_id", "occurred_at"),
        Index("ix_audit_events_event_type", "event_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workflow_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_runs.id"))
    event_type: Mapped[str] = mapped_column(String(100))
    stage: Mapped[str | None] = mapped_column(String(100))
    actor_type: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[str | None] = mapped_column(String(255))
    details_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    workflow: Mapped[WorkflowRun | None] = relationship(back_populates="audit_events")


from app.database.models.workflow_run import WorkflowRun  # noqa: E402
