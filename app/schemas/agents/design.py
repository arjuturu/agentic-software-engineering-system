from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from app.schemas.agents.common import AgentInput


class DesignStatus(StrEnum):
    DESIGN_COMPLETE = "DESIGN_COMPLETE"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    BLOCKED = "BLOCKED"


class DesignAgentInput(AgentInput):
    approved_requirement: dict[str, Any]


class DesignOutput(BaseModel):
    architecture_summary: str
    components: list[dict[str, Any]]
    api_design: list[dict[str, Any]]
    data_design: list[dict[str, Any]]
    control_flow: list[str]
    security_controls: list[str]
    reliability_controls: list[str]
    observability_controls: list[str]
    architecture_decisions: list[dict[str, Any]]
    risks: list[str]
    trade_offs: list[str]
    limitations: list[str]
    implementation_feasible: bool
    status: DesignStatus
