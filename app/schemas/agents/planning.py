from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.agents.common import AgentInput, RiskLevel
from app.tools.models import CommandId


class PlanningStatus(StrEnum):
    PLAN_COMPLETE = "PLAN_COMPLETE"
    DESIGN_REVISION_REQUIRED = "DESIGN_REVISION_REQUIRED"
    BLOCKED = "BLOCKED"


class PlanTask(BaseModel):
    task_id: str = Field(pattern=r"^TASK-[0-9]{3}$")
    title: str
    description: str
    task_type: str
    dependencies: list[str]
    parallel_group: str | None
    risk_level: RiskLevel
    expected_files: list[str]
    allowed_paths: list[str]
    entry_criteria: list[str]
    exit_criteria: list[str]
    validation_commands: list[CommandId]
    acceptance_criteria_covered: list[str]


class PlanningAgentInput(AgentInput):
    approved_requirement: dict[str, Any]
    architecture_design: dict[str, Any]
    scenario_path_policy: dict[str, Any]
    pre_satisfied_capabilities: list[str] = Field(default_factory=list)
    pending_orchestration_gate: str = "ARCHITECTURE_AND_PLAN"
    post_approval_plan: bool = True
    generated_task_ids: list[str] = Field(default_factory=list)
    execution_order: list[str] = Field(default_factory=list)
    validation_errors: list[dict[str, Any]] = Field(default_factory=list)
    previous_plan: dict[str, Any] = Field(default_factory=dict)


class PlanningOutput(BaseModel):
    plan_summary: str
    tasks: list[PlanTask]
    execution_order: list[str]
    parallel_groups: list[list[str]]
    critical_path: list[str]
    high_risk_tasks: list[str]
    assumptions: list[str]
    implementation_risks: list[str]
    status: PlanningStatus
