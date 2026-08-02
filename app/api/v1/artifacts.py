from fastapi import APIRouter

from app.api.v1.workflows import WorkflowServiceDependency
from app.schemas.artifacts import ArtifactContentResponse, ArtifactRecordResponse

router = APIRouter(prefix="/api/v1/workflows", tags=["artifacts"])


@router.get(
    "/{workflow_id}/artifacts",
    response_model=list[ArtifactRecordResponse],
    response_model_by_alias=True,
)
def list_artifacts(workflow_id: str, service: WorkflowServiceDependency) -> list[dict]:
    service.get(workflow_id)
    return [
        {
            "fileName": item.file_name,
            "artifactType": item.artifact_type,
            "version": item.version,
            "status": item.status,
        }
        for item in service.runtime.artifacts.list(workflow_id)
    ]


@router.get(
    "/{workflow_id}/artifacts/{file_name}",
    response_model=ArtifactContentResponse,
    response_model_by_alias=True,
)
def read_artifact(workflow_id: str, file_name: str, service: WorkflowServiceDependency) -> dict:
    service.get(workflow_id)
    return {
        "fileName": file_name,
        "content": service.runtime.artifacts.read(workflow_id, file_name),
    }
