from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ToolStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    PARTIAL = "PARTIAL"


class ToolError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class CommandId(StrEnum):
    PYTEST = "PYTEST"
    RUFF_CHECK = "RUFF_CHECK"
    ALEMBIC_CURRENT = "ALEMBIC_CURRENT"
    ALEMBIC_HISTORY = "ALEMBIC_HISTORY"
    ALEMBIC_UPGRADE_HEAD = "ALEMBIC_UPGRADE_HEAD"
    ALEMBIC_DOWNGRADE_BASE = "ALEMBIC_DOWNGRADE_BASE"
    PYTHON_VERSION = "PYTHON_VERSION"
    TARGET_IMPORT_CHECK = "TARGET_IMPORT_CHECK"
    TARGET_OPENAPI_CHECK = "TARGET_OPENAPI_CHECK"


class CommandResult(BaseModel):
    command_id: str
    status: ToolStatus
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    truncated: bool = False
    error: ToolError | None = None


class FileOperationResult(BaseModel):
    path: str
    operation: str
    status: ToolStatus
    previous_hash: str | None = None
    resulting_hash: str | None = None
    error: ToolError | None = None


class BatchEditResult(BaseModel):
    status: ToolStatus
    operations: list[FileOperationResult]
    rolled_back: bool
    error: ToolError | None = None


class GitOperationResult(BaseModel):
    operation: str
    status: ToolStatus
    current_branch: str | None = None
    commit_id: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    error: ToolError | None = None


class RepositoryScanResult(BaseModel):
    repository_path: str
    status: ToolStatus
    is_git_repository: bool
    current_branch: str | None = None
    file_count: int = 0
    directory_count: int = 0
    file_extensions: dict[str, int] = Field(default_factory=dict)
    detected_project_files: list[str] = Field(default_factory=list)
    detected_python_packages: list[str] = Field(default_factory=list)
    detected_test_files: list[str] = Field(default_factory=list)
    detected_migration_files: list[str] = Field(default_factory=list)
    fastapi_files: list[str] = Field(default_factory=list)
    sqlalchemy_files: list[str] = Field(default_factory=list)
    restricted_files_found: list[str] = Field(default_factory=list)
    skipped_files: list[str] = Field(default_factory=list)
    repository_summary: str = ""
    error: ToolError | None = None


class WorkspaceResult(BaseModel):
    name: str
    path: str
    status: ToolStatus
    created: bool = False
    error: ToolError | None = None


class EditOperation(StrEnum):
    CREATE = "CREATE"
    MODIFY = "MODIFY"


class StructuredEdit(BaseModel):
    operation: EditOperation
    relative_path: str
    content: str | None = None
    expected_absent: bool = True
    expected_hash: str | None = None
    old_text: str | None = None
    replacement_text: str | None = None


class ValidationSuiteResult(BaseModel):
    status: ToolStatus
    ruff: CommandResult
    pytest: CommandResult | None = None
    failed_step: str | None = None


class MigrationValidationResult(BaseModel):
    status: ToolStatus
    steps: list[CommandResult]
    failed_step: str | None = None
    final_revision: str | None = None


class ArtifactWriteResult(BaseModel):
    workflow_id: str
    artifact_path: str
    status: ToolStatus
    content_hash: str | None = None
    error: ToolError | None = None
