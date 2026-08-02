from fastapi import APIRouter

from app.api.v1.workflows import WorkflowServiceDependency
from app.schemas.artifacts import AuditEventResponse

router = APIRouter(prefix="/api/v1/workflows", tags=["audit"])


@router.get(
    "/{workflow_id}/audit", response_model=list[AuditEventResponse], response_model_by_alias=True
)
def audit_history(workflow_id: str, service: WorkflowServiceDependency) -> list[dict]:
    service.get(workflow_id)
    return [
        {
            "eventType": item.event_type,
            "stage": item.stage,
            "actorType": item.actor_type,
            "actorId": item.actor_id,
            "details": item.details_json,
            "occurredAt": item.occurred_at.isoformat(),
        }
        for item in service.runtime.audit.list(workflow_id)
    ]
