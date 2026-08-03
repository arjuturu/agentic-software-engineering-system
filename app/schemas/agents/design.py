from enum import StrEnum

from pydantic import BaseModel

from app.schemas.agents.common import AgentInput


class DesignStatus(StrEnum):
    DESIGN_COMPLETE = "DESIGN_COMPLETE"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    BLOCKED = "BLOCKED"


class DesignAgentInput(AgentInput):
    approved_requirement: dict[str, object]


class ArchitectureComponent(BaseModel):
    name: str
    responsibility: str
    interfaces: list[str]
    dependencies: list[str]


class ApiDesignItem(BaseModel):
    name: str
    method_or_type: str
    path_or_signature: str
    purpose: str


class DataDesignItem(BaseModel):
    entity: str
    purpose: str
    fields: list[str]
    relationships: list[str]
    constraints: list[str]


class ArchitectureDecision(BaseModel):
    decision: str
    rationale: str
    alternatives: list[str]
    consequences: list[str]


class DesignOutput(BaseModel):
    architecture_summary: str
    components: list[ArchitectureComponent]
    api_design: list[ApiDesignItem]
    data_design: list[DataDesignItem]
    control_flow: list[str]
    security_controls: list[str]
    reliability_controls: list[str]
    observability_controls: list[str]
    architecture_decisions: list[ArchitectureDecision]
    risks: list[str]
    trade_offs: list[str]
    limitations: list[str]
    implementation_feasible: bool
    status: DesignStatus
