from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agents.common import ScenarioType, ScriptedScenario, WorkflowStatus


class WorkflowCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    scenario_type: ScenarioType = Field(alias="scenarioType")
    requirement: str = Field(min_length=1, max_length=10000)
    workspace_name: str = Field(
        alias="workspaceName",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$",
    )
    scripted_scenario: ScriptedScenario = Field(
        default=ScriptedScenario.HAPPY_PATH, alias="scriptedScenario"
    )


class ClarificationAnswer(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    question_id: str = Field(alias="questionId", pattern=r"^Q-[0-9]{3}$")
    answer: str = Field(min_length=1, max_length=2000)


class ClarificationSubmitRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(default="CLARIFICATION_RESPONSE", pattern="^CLARIFICATION_RESPONSE$")
    workflow_id: str = Field(alias="workflowId", min_length=1, max_length=64)
    clarification_id: str = Field(alias="clarificationId", min_length=1, max_length=64)
    state_version: int = Field(alias="stateVersion", ge=1)
    answers: list[ClarificationAnswer] = Field(min_length=1)


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    workflow_id: str = Field(alias="workflowId")
    thread_id: str = Field(alias="threadId")
    status: WorkflowStatus
    current_stage: str = Field(alias="currentStage")
    state_version: int = Field(alias="stateVersion")
    workspace_path: str = Field(alias="workspacePath")
    scenario_profile: dict[str, Any] = Field(default_factory=dict, alias="scenarioProfile")
    requirement_version: int = Field(default=1, alias="requirementVersion")
    architecture_version: int = Field(default=0, alias="architectureVersion")
    plan_version: int = Field(default=0, alias="planVersion")
    retry_counts: dict[str, int] = Field(default_factory=dict, alias="retryCounts")
    pending_interaction: dict[str, Any] = Field(default_factory=dict, alias="pendingInteraction")
    pending_approval: dict[str, Any] = Field(default_factory=dict, alias="pendingApproval")
    final_release_status: str = Field(default="", alias="finalReleaseStatus")
    started_at: datetime | str = Field(alias="startedAt")
    updated_at: datetime | str = Field(alias="updatedAt")
    completed_at: datetime | str | None = Field(default=None, alias="completedAt")
