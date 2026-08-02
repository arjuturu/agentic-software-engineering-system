from enum import StrEnum

from pydantic import BaseModel

from app.schemas.agents.common import AgentInput, FailureCategory


class ValidationStatus(StrEnum):
    VALIDATION_PASSED = "VALIDATION_PASSED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    SAFE_STOP_REQUIRED = "SAFE_STOP_REQUIRED"


class ValidationAgentInput(AgentInput):
    command_results: list[dict[str, object]]
    implementation_result: dict[str, object]


class AcceptanceCriterionResult(BaseModel):
    criterion: str
    passed: bool
    evidence: list[str]


class ValidationOutput(BaseModel):
    acceptance_criteria_results: list[AcceptanceCriterionResult]
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
