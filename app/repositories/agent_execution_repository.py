from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.database.models import AgentExecution


class AgentExecutionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def start(self, workflow_id: str, agent_name: str, stage: str, attempt: int) -> AgentExecution:
        item = AgentExecution(
            workflow_id=workflow_id,
            agent_name=agent_name,
            stage=stage,
            status="RUNNING",
            attempt_number=attempt,
        )
        self.session.add(item)
        self.session.flush()
        return item

    def finish(self, item: AgentExecution, output_artifact: str | None = None) -> None:
        item.status = "COMPLETED"
        item.output_artifact = output_artifact
        item.completed_at = utc_now()

    def fail(self, item: AgentExecution, message: str) -> None:
        item.status = "FAILED"
        item.error_message = message[:1000]
        item.completed_at = utc_now()
