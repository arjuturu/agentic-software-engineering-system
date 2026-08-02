from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agents.common import ApprovalAction, ApprovalGate


class ApprovalSubmitRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(default="APPROVAL_DECISION", pattern="^APPROVAL_DECISION$")
    gate_type: ApprovalGate = Field(alias="gateType")
    state_version: int = Field(alias="stateVersion", ge=1)
    action: ApprovalAction
    comments: str | None = Field(default=None, max_length=2000)
    conditions: list[str] = Field(default_factory=list)
    decided_by: str = Field(default="local-user", alias="decidedBy", min_length=1, max_length=255)


class ApprovalRecordResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    approval_id: str = Field(alias="approvalId")
    workflow_id: str = Field(alias="workflowId")
    gate_type: ApprovalGate = Field(alias="gateType")
    state_version: int = Field(alias="stateVersion")
    action: ApprovalAction
    decided_by: str = Field(alias="decidedBy")
