from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import WorkflowArtifact


class ArtifactRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def next_version(self, workflow_id: str, artifact_type: str) -> int:
        value = self.session.scalar(
            select(func.max(WorkflowArtifact.version)).where(
                WorkflowArtifact.workflow_id == workflow_id,
                WorkflowArtifact.artifact_type == artifact_type,
            )
        )
        return int(value or 0) + 1

    def add(
        self, workflow_id: str, artifact_type: str, name: str, path: str, version: int
    ) -> WorkflowArtifact:
        item = WorkflowArtifact(
            workflow_id=workflow_id,
            artifact_type=artifact_type,
            file_name=name,
            file_path=path,
            version=version,
            status="ACTIVE",
        )
        self.session.add(item)
        self.session.flush()
        return item

    def list(self, workflow_id: str) -> list[WorkflowArtifact]:
        return list(
            self.session.scalars(
                select(WorkflowArtifact)
                .where(WorkflowArtifact.workflow_id == workflow_id)
                .order_by(WorkflowArtifact.created_at, WorkflowArtifact.file_name)
            )
        )

    def get(self, workflow_id: str, file_name: str) -> WorkflowArtifact | None:
        return self.session.scalar(
            select(WorkflowArtifact).where(
                WorkflowArtifact.workflow_id == workflow_id,
                WorkflowArtifact.file_name == file_name,
            )
        )
