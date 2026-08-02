from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.database.base import Base


class WorkflowTask(Base):
    __tablename__ = "workflow_tasks"
    __table_args__ = (
        UniqueConstraint("workflow_id", "task_key", name="uq_workflow_tasks_workflow_task_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"))
    task_key: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    task_type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40))
    dependencies_json: Mapped[list[object]] = mapped_column(
        MutableList.as_mutable(JSON), default=list
    )
    expected_files_json: Mapped[list[object]] = mapped_column(
        MutableList.as_mutable(JSON), default=list
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    workflow: Mapped[WorkflowRun] = relationship(back_populates="tasks")


from app.database.models.workflow_run import WorkflowRun  # noqa: E402
