from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.agents.common import AgentInput
from app.tools.models import StructuredEdit


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
    implementation_plan: dict[str, Any]
    repository_analysis: dict[str, Any]
    validation_failure: dict[str, Any] | None = None
    file_hashes: dict[str, str] = Field(default_factory=dict)


class CodingOutput(BaseModel):
    implementation_summary: str
    change_plan: list[dict[str, Any]]
    structured_edits: list[StructuredEdit]
    tests_created_or_modified: list[str]
    migrations_created: list[str]
    assumptions: list[str]
    risks: list[str]
    dependency_changes: list[str]
    high_risk_change: bool
    high_risk_reason: str | None = None
    status: CodingStatus
    replan_reason: str | None = None
