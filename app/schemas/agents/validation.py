from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from app.schemas.agents.common import AgentInput, FailureCategory


class ValidationStatus(StrEnum):
    VALIDATION_PASSED = "VALIDATION_PASSED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    SAFE_STOP_REQUIRED = "SAFE_STOP_REQUIRED"


class ValidationAgentInput(AgentInput):
    command_results: list[dict[str, Any]]
    implementation_result: dict[str, Any]


class ValidationOutput(BaseModel):
    acceptance_criteria_results: list[dict[str, Any]]
    tests_executed: int
    tests_passed: int
    tests_failed: int
    tests_skipped: int
    lint_status: str
    migration_status: str
    architecture_compliance: bool
    findings: list[str]
    failure_category: FailureCategory | None = None
    retry_recommended: bool
    replan_recommended: bool
    rollback_recommended: bool
    release_recommendation: str
    status: ValidationStatus
