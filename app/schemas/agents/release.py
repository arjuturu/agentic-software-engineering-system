from typing import Any

from pydantic import BaseModel

from app.schemas.agents.common import AgentInput, WorkflowStatus


class ReleaseAgentInput(AgentInput):
    validation_result: dict[str, Any]
    documentation_draft: dict[str, Any]


class ReleaseOutput(BaseModel):
    change_summary: str
    requirement_completion_summary: str
    architecture_summary: str
    implementation_summary: str
    testing_summary: str
    security_summary: str
    changed_files: list[str]
    generated_artifacts: list[str]
    known_risks: list[str]
    known_limitations: list[str]
    conditions_for_release: list[str]
    rollback_instructions: list[str]
    recommended_status: WorkflowStatus
    recommendation_reason: str
