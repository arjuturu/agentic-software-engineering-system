from fastapi import APIRouter

from app.api.v1.workflows import WorkflowServiceDependency
from app.schemas.approvals import ApprovalSubmitRequest
from app.schemas.workflows import WorkflowResponse

router = APIRouter(prefix="/api/v1/workflows", tags=["approvals"])


@router.post(
    "/{workflow_id}/approvals/{approval_id}",
    response_model=WorkflowResponse,
    response_model_by_alias=True,
)
def submit_approval(
    workflow_id: str,
    approval_id: str,
    payload: ApprovalSubmitRequest,
    service: WorkflowServiceDependency,
) -> dict:
    return service.approve(workflow_id, approval_id, payload.model_dump(mode="json", by_alias=True))
