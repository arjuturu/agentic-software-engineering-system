from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.schemas.agents.common import AgentInput
from app.tools.models import EditOperation


class RepositoryAnalysisStatus(StrEnum):
    ANALYSIS_COMPLETE = "ANALYSIS_COMPLETE"
    INCOMPATIBLE = "INCOMPATIBLE"
    BLOCKED = "BLOCKED"


class CodingStatus(StrEnum):
    READY_TO_APPLY = "READY_TO_APPLY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    BLOCKED = "BLOCKED"


class RepositoryAnalysisInput(AgentInput):
    deterministic_scan: dict[str, Any]


class RepositoryAnalysisOutput(BaseModel):
    repository_summary: str
    detected_frameworks: list[str]
    project_structure: list[str]
    impacted_modules: list[str]
    impacted_files: list[str]
    existing_tests: list[str]
    existing_migrations: list[str]
    coding_conventions: list[str]
    compatibility_risks: list[str]
    recommended_allowed_paths: list[str]
    blocked_or_sensitive_paths: list[str]
    architecture_compatible: bool
    status: RepositoryAnalysisStatus


class CodingAgentInput(AgentInput):
    implementation_plan: dict[str, object]
    active_task: dict[str, object]
    repository_analysis: dict[str, object]
    validation_failure: dict[str, object] | None = None
    file_hashes: dict[str, str] = Field(default_factory=dict)
    repository_context: list[dict[str, object]] = Field(default_factory=list)
    originating_task: dict[str, object] | None = None


class CodingEdit(BaseModel):
    operation: EditOperation
    relative_path: str
    content: str | None
    expected_absent: bool
    expected_hash: str | None
    old_text: str | None
    replacement_text: str | None

    @model_validator(mode="after")
    def validate_modify_mode(self) -> "CodingEdit":
        if self.operation != EditOperation.MODIFY:
            return self
        full_file = (
            self.content is not None
            and self.old_text is None
            and self.replacement_text is None
        )
        targeted = (
            self.content is None
            and self.old_text is not None
            and self.replacement_text is not None
        )
        if not self.expected_hash or full_file == targeted:
            raise ValueError("MODIFY must use exactly one hash-guarded edit mode")
        return self


class ChangePlanItem(BaseModel):
    task_id: str
    paths: list[str]


class CodingOutput(BaseModel):
    implementation_summary: str
    change_plan: list[ChangePlanItem]
    structured_edits: list[CodingEdit]
    tests_created_or_modified: list[str]
    migrations_created: list[str]
    assumptions: list[str]
    risks: list[str]
    dependency_changes: list[str]
    high_risk_change: bool
    high_risk_reason: str | None = None
    status: CodingStatus
    replan_reason: str | None = None
