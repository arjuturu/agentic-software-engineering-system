import hashlib
import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from app.tools.models import ArtifactWriteResult, ToolError, ToolStatus
from app.tools.path_policy import PathPolicy, PathPolicyError

logger = logging.getLogger(__name__)

_WORKFLOW_PATTERN = re.compile(r"^WF-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_FILE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ALLOWED_EXTENSIONS = {".md", ".json", ".txt", ".diff"}


class ArtifactWriter:
    """Write bounded workflow artifacts beneath the configured artifact root."""

    def __init__(self, path_policy: PathPolicy) -> None:
        self.path_policy = path_policy

    @staticmethod
    def _validate_workflow_id(workflow_id: str) -> None:
        if not _WORKFLOW_PATTERN.fullmatch(workflow_id):
            raise PathPolicyError("The workflow identifier is invalid.", "INVALID_WORKFLOW_ID")

    @staticmethod
    def _validate_file_name(file_name: str) -> None:
        path = Path(file_name)
        if (
            not _FILE_PATTERN.fullmatch(file_name)
            or path.name != file_name
            or path.suffix.lower() not in _ALLOWED_EXTENSIONS
        ):
            raise PathPolicyError("The artifact file name is invalid.", "INVALID_ARTIFACT_NAME")

    def create_workflow_directory(self, workflow_id: str) -> Path:
        """Create and return a validated workflow artifact directory."""
        self._validate_workflow_id(workflow_id)
        directory = self.path_policy.resolve_artifact_path(workflow_id)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=path.parent,
                prefix=f".{path.name}.",
                delete=False,
            ) as stream:
                temporary_name = stream.name
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, path)
            temporary_name = None
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)

    def write_text_artifact(
        self,
        workflow_id: str,
        file_name: str,
        content: str,
        overwrite: bool = False,
    ) -> ArtifactWriteResult:
        """Atomically write a UTF-8 text artifact without overwriting by default."""
        try:
            self._validate_workflow_id(workflow_id)
            self._validate_file_name(file_name)
            directory = self.create_workflow_directory(workflow_id)
            path = self.path_policy.validate_write_path(directory / file_name)
            if path.exists() and not overwrite:
                raise PathPolicyError("The artifact already exists.", "ARTIFACT_ALREADY_EXISTS")
            self._atomic_write(path, content)
            reference = f"{workflow_id}/{file_name}"
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            logger.info(
                "tool=artifact_writer operation=write status=SUCCESS workflow=%s", workflow_id
            )
            return ArtifactWriteResult(
                workflow_id=workflow_id,
                artifact_path=reference,
                status=ToolStatus.SUCCESS,
                content_hash=digest,
            )
        except (PathPolicyError, OSError) as exc:
            code = exc.error_code if isinstance(exc, PathPolicyError) else "ARTIFACT_WRITE_FAILED"
            logger.warning(
                "tool=artifact_writer operation=write status=BLOCKED error_code=%s", code
            )
            return ArtifactWriteResult(
                workflow_id=workflow_id,
                artifact_path="",
                status=ToolStatus.BLOCKED,
                error=ToolError(code=code, message="The artifact could not be written."),
            )

    def write_json_artifact(
        self,
        workflow_id: str,
        file_name: str,
        content: dict[str, Any],
        overwrite: bool = False,
    ) -> ArtifactWriteResult:
        """Serialize and atomically write a deterministic JSON artifact."""
        try:
            serialized = json.dumps(content, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        except (TypeError, ValueError):
            logger.exception(
                "tool=artifact_writer operation=json status=FAILED error_code=JSON_INVALID"
            )
            return ArtifactWriteResult(
                workflow_id=workflow_id,
                artifact_path="",
                status=ToolStatus.FAILED,
                error=ToolError(
                    code="JSON_INVALID", message="The artifact content is not JSON serializable."
                ),
            )
        return self.write_text_artifact(workflow_id, file_name, serialized, overwrite)

    def read_artifact(self, workflow_id: str, file_name: str) -> str:
        """Read a validated UTF-8 workflow artifact."""
        self._validate_workflow_id(workflow_id)
        self._validate_file_name(file_name)
        path = self.path_policy.resolve_artifact_path(f"{workflow_id}/{file_name}")
        path = self.path_policy.validate_read_path(path)
        if not path.is_file():
            raise PathPolicyError("The artifact does not exist.", "ARTIFACT_NOT_FOUND")
        return path.read_text(encoding="utf-8")


