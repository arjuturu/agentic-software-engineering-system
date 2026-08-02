from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import AuditEvent


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        workflow_id: str,
        event_type: str,
        stage: str | None,
        details: dict | None = None,
        *,
        actor_type: str = "SYSTEM",
        actor_id: str | None = None,
    ) -> AuditEvent:
        item = AuditEvent(
            workflow_id=workflow_id,
            event_type=event_type,
            stage=stage,
            actor_type=actor_type,
            actor_id=actor_id,
            details_json=details,
        )
        self.session.add(item)
        self.session.flush()
        return item

    def list(self, workflow_id: str) -> list[AuditEvent]:
        return list(
            self.session.scalars(
                select(AuditEvent)
                .where(AuditEvent.workflow_id == workflow_id)
                .order_by(AuditEvent.occurred_at, AuditEvent.id)
            )
        )

    def exists(self, workflow_id: str, event_type: str, stage: str | None) -> bool:
        return (
            self.session.scalar(
                select(AuditEvent.id)
                .where(
                    AuditEvent.workflow_id == workflow_id,
                    AuditEvent.event_type == event_type,
                    AuditEvent.stage == stage,
                )
                .limit(1)
            )
            is not None
        )
