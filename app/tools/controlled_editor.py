import hashlib
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings, get_settings
from app.tools.models import (
    BatchEditResult,
    EditOperation,
    FileOperationResult,
    StructuredEdit,
    ToolError,
    ToolStatus,
)
from app.tools.path_policy import PathPolicy, PathPolicyError

logger = logging.getLogger(__name__)

_ALLOWED_EXTENSIONS = {".py", ".md", ".txt", ".toml", ".ini", ".yaml", ".yml", ".json"}
_ALLOWED_EXTENSIONLESS = {"README", "LICENSE", "Makefile", "Dockerfile"}
_ALLOWED_SPECIAL = {".env.example", ".gitignore"}


@dataclass(frozen=True)
class _PreparedEdit:
    edit: StructuredEdit
    path: Path
    relative_path: str
    previous: bytes | None
    resulting: bytes


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


class ControlledEditor:
    """Apply validated create and exact hash-guarded modify operations atomically."""

    def __init__(self, path_policy: PathPolicy, settings: Settings | None = None) -> None:
        self.path_policy = path_policy
        self.max_file_bytes = (settings or get_settings()).MAX_EDIT_FILE_BYTES

    @staticmethod
    def _extension_allowed(path: Path) -> bool:
        if path.name in _ALLOWED_SPECIAL or path.name in _ALLOWED_EXTENSIONLESS:
            return True
        return path.suffix.lower() in _ALLOWED_EXTENSIONS

    def _check_content_size(self, content: bytes) -> None:
        if len(content) > self.max_file_bytes:
            raise PathPolicyError("Edit content exceeds the configured limit.", "EDIT_TOO_LARGE")

    def _prepare_create(self, workspace: Path, edit: StructuredEdit) -> _PreparedEdit:
        path = self.path_policy.validate_relative_path(
            workspace, edit.relative_path, operation="write"
        )
        if not self._extension_allowed(path):
            raise PathPolicyError("The requested file type is not allowed.", "FILE_TYPE_BLOCKED")
        if not edit.expected_absent:
            raise PathPolicyError("Create operations must expect file absence.", "INVALID_CREATE")
        if path.exists():
            raise PathPolicyError("The file already exists.", "FILE_ALREADY_EXISTS")
        if edit.content is None:
            raise PathPolicyError("Create content is required.", "MISSING_CONTENT")
        resulting = edit.content.encode("utf-8")
        self._check_content_size(resulting)
        return _PreparedEdit(edit, path, edit.relative_path, None, resulting)

    def _prepare_modify(self, workspace: Path, edit: StructuredEdit) -> _PreparedEdit:
        path = self.path_policy.validate_relative_path(workspace, edit.relative_path)
        if not path.is_file():
            raise PathPolicyError("The requested path is not a file.", "NOT_A_FILE")
        if not self._extension_allowed(path):
            raise PathPolicyError("The requested file type is not allowed.", "FILE_TYPE_BLOCKED")
        if not edit.expected_hash:
            raise PathPolicyError("Modify guards are incomplete.", "INVALID_MODIFY")
        previous = path.read_bytes()
        if sha256_bytes(previous) != edit.expected_hash.lower():
            raise PathPolicyError(
                "The expected file hash is stale.",
                "HASH_MISMATCH",
                details={"failure_category": "STALE_EDIT_CONTEXT"},
            )
        if edit.content is not None:
            resulting = edit.content.encode("utf-8")
            self._check_content_size(resulting)
            return _PreparedEdit(edit, path, edit.relative_path, previous, resulting)
        try:
            existing_text = previous.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PathPolicyError(
                "Only UTF-8 text files can be modified.", "INVALID_ENCODING"
            ) from exc
        occurrences = existing_text.count(edit.old_text)
        if occurrences == 0:
            raise PathPolicyError(
                "The exact old text was not found.",
                "EDIT_CONFLICT",
                details={"failure_category": "TEXT_NOT_FOUND"},
            )
        if occurrences > 1:
            raise PathPolicyError(
                "The exact old text is ambiguous.",
                "EDIT_CONFLICT",
                details={"failure_category": "MULTIPLE_MATCHES"},
            )
        resulting = existing_text.replace(edit.old_text, edit.replacement_text, 1).encode("utf-8")
        self._check_content_size(resulting)
        return _PreparedEdit(edit, path, edit.relative_path, previous, resulting)

    def _prepare(self, workspace: Path, edit: StructuredEdit) -> _PreparedEdit:
        if edit.operation == EditOperation.CREATE:
            return self._prepare_create(workspace, edit)
        if edit.operation == EditOperation.MODIFY:
            return self._prepare_modify(workspace, edit)
        raise PathPolicyError("The edit operation is unsupported.", "OPERATION_BLOCKED")

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
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

    @staticmethod
    def _restore(path: Path, content: bytes | None) -> None:
        if content is None:
            path.unlink(missing_ok=True)
            return
        ControlledEditor._atomic_write(path, content)

    def apply_batch(
        self,
        workspace: Path,
        edits: list[StructuredEdit],
        *,
        allowed_paths: list[str] | None = None,
        policy_context: dict[str, object] | None = None,
    ) -> BatchEditResult:
        """Validate all edits, then apply them with rollback on any write failure."""
        try:
            safe_workspace = self.path_policy.validate_working_directory(workspace)
            if not edits:
                raise PathPolicyError("At least one edit is required.", "EMPTY_BATCH")
            if len({edit.relative_path for edit in edits}) != len(edits):
                raise PathPolicyError("A batch cannot edit the same path twice.", "DUPLICATE_PATH")
            if allowed_paths is not None:
                effective_paths = self.path_policy.normalize_policy_paths(allowed_paths)
                for edit in edits:
                    self.path_policy.validate_allowed_path(edit.relative_path, effective_paths)
            prepared = [self._prepare(safe_workspace, edit) for edit in edits]
        except (PathPolicyError, OSError) as exc:
            code = exc.error_code if isinstance(exc, PathPolicyError) else "EDIT_VALIDATION_FAILED"
            logger.warning(
                "tool=controlled_editor operation=batch status=BLOCKED error_code=%s", code
            )
            return BatchEditResult(
                status=ToolStatus.BLOCKED,
                operations=[],
                rolled_back=False,
                error=ToolError(
                    code=code,
                    message="The edit batch was blocked.",
                    details={
                        **(policy_context or {}),
                        **(exc.details if isinstance(exc, PathPolicyError) else {}),
                    },
                ),
            )

        results = [
            FileOperationResult(
                path=item.relative_path,
                operation=item.edit.operation.value,
                status=ToolStatus.SUCCESS,
                previous_hash=sha256_bytes(item.previous) if item.previous is not None else None,
                resulting_hash=sha256_bytes(item.resulting),
            )
            for item in prepared
        ]
        applied: list[_PreparedEdit] = []
        try:
            for item in prepared:
                self._atomic_write(item.path, item.resulting)
                applied.append(item)
        except OSError:
            logger.exception(
                "tool=controlled_editor operation=batch status=FAILED error_code=WRITE_FAILED"
            )
            rollback_failed = False
            for item in reversed(applied):
                try:
                    self._restore(item.path, item.previous)
                except OSError:
                    rollback_failed = True
                    logger.exception(
                        "tool=controlled_editor operation=rollback status=FAILED "
                        "error_code=ROLLBACK_FAILED"
                    )
            for result in results:
                result.status = ToolStatus.FAILED
                result.error = ToolError(
                    code="ROLLED_BACK", message="The batch was restored after a write failure."
                )
            return BatchEditResult(
                status=ToolStatus.FAILED,
                operations=results,
                rolled_back=not rollback_failed,
                error=ToolError(
                    code="WRITE_FAILED",
                    message="The edit batch failed and rollback was attempted.",
                ),
            )

        logger.info(
            "tool=controlled_editor operation=batch status=SUCCESS operations=%d",
            len(results),
        )
        return BatchEditResult(status=ToolStatus.SUCCESS, operations=results, rolled_back=False)
