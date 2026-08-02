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
    parallel_group: str | None = None
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
