from sqlalchemy.orm import Session, sessionmaker

from app.repositories.workflow_repository import WorkflowRepository


class WorkflowStatusService:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def persist(self, workflow_id: str, state: dict) -> None:
        with self.sessions.begin() as session:
            WorkflowRepository(session).update_state(workflow_id, state)
