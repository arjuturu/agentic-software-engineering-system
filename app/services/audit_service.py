from sqlalchemy.orm import Session, sessionmaker

from app.repositories.audit_repository import AuditRepository


class AuditService:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def record(
        self,
        workflow_id: str,
        event_type: str,
        stage: str | None,
        details: dict | None = None,
        *,
        actor_type: str = "SYSTEM",
        actor_id: str | None = None,
    ) -> None:
        with self.sessions.begin() as session:
            AuditRepository(session).add(
                workflow_id, event_type, stage, details, actor_type=actor_type, actor_id=actor_id
            )

    def list(self, workflow_id: str):
        with self.sessions() as session:
            return AuditRepository(session).list(workflow_id)
