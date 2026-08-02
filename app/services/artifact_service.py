from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.artifacts.renderer import render_artifact
from app.artifacts.writer import ArtifactWriter
from app.core.exceptions import ApplicationError
from app.repositories.artifact_repository import ArtifactRepository
from app.tools.models import ToolStatus


class ArtifactService:
    def __init__(self, sessions: sessionmaker[Session], writer: ArtifactWriter) -> None:
        self.sessions = sessions
        self.writer = writer

    def _name(self, base_name: str, version: int) -> str:
        path = Path(base_name)
        return base_name if version == 1 else f"{path.stem}-v{version}{path.suffix}"

    def write_json(
        self, workflow_id: str, artifact_type: str, base_name: str, content: dict[str, Any]
    ) -> str:
        with self.sessions.begin() as session:
            repository = ArtifactRepository(session)
            version = repository.next_version(workflow_id, artifact_type)
            name = self._name(base_name, version)
            result = self.writer.write_json_artifact(workflow_id, name, content)
            if result.status != ToolStatus.SUCCESS:
                raise ApplicationError(
                    "The workflow artifact could not be written.", "ARTIFACT_WRITE_FAILED", 500
                )
            repository.add(workflow_id, artifact_type, name, result.artifact_path, version)
            return result.artifact_path

    def write_markdown(
        self,
        workflow_id: str,
        artifact_type: str,
        base_name: str,
        content: dict[str, Any],
        evidence: list[str] | None = None,
    ) -> str:
        with self.sessions.begin() as session:
            repository = ArtifactRepository(session)
            version = repository.next_version(workflow_id, artifact_type)
            name = self._name(base_name, version)
            rendered = render_artifact(base_name, workflow_id, version, content, evidence)
            result = self.writer.write_text_artifact(workflow_id, name, rendered)
            if result.status != ToolStatus.SUCCESS:
                raise ApplicationError(
                    "The workflow artifact could not be written.", "ARTIFACT_WRITE_FAILED", 500
                )
            repository.add(workflow_id, artifact_type, name, result.artifact_path, version)
            return result.artifact_path

    def write_text(self, workflow_id: str, artifact_type: str, base_name: str, content: str) -> str:
        with self.sessions.begin() as session:
            repository = ArtifactRepository(session)
            version = repository.next_version(workflow_id, artifact_type)
            name = self._name(base_name, version)
            result = self.writer.write_text_artifact(workflow_id, name, content)
            if result.status != ToolStatus.SUCCESS:
                raise ApplicationError(
                    "The workflow artifact could not be written.", "ARTIFACT_WRITE_FAILED", 500
                )
            repository.add(workflow_id, artifact_type, name, result.artifact_path, version)
            return result.artifact_path

    def list(self, workflow_id: str):
        with self.sessions() as session:
            return ArtifactRepository(session).list(workflow_id)

    def read(self, workflow_id: str, file_name: str) -> str:
        with self.sessions() as session:
            if ArtifactRepository(session).get(workflow_id, file_name) is None:
                raise ApplicationError("The artifact was not found.", "ARTIFACT_NOT_FOUND", 404)
        return self.writer.read_artifact(workflow_id, file_name)
