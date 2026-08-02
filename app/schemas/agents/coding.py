from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

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


class CodingEdit(BaseModel):
    operation: EditOperation
    relative_path: str
    content: str | None
    expected_absent: bool
    expected_hash: str | None
    old_text: str | None
    replacement_text: str | None


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
