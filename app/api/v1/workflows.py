from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.schemas.workflows import (
    ClarificationSubmitRequest,
    WorkflowCreateRequest,
    WorkflowResponse,
)
from app.services.workflow_service import WorkflowService

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


def get_workflow_service(request: Request) -> WorkflowService:
    return request.app.state.workflow_service


WorkflowServiceDependency = Annotated[WorkflowService, Depends(get_workflow_service)]


@router.post("", response_model=WorkflowResponse, response_model_by_alias=True, status_code=201)
def create_workflow(
    payload: WorkflowCreateRequest, service: WorkflowServiceDependency, request: Request
) -> dict:
    return service.create(payload, getattr(request.state, "correlation_id", None))


@router.post(
    "/{workflow_id}/retry",
    response_model=WorkflowResponse,
    response_model_by_alias=True,
)
def retry_workflow(workflow_id: str, service: WorkflowServiceDependency) -> dict:
    return service.retry(workflow_id)


@router.get("/{workflow_id}", response_model=WorkflowResponse, response_model_by_alias=True)
def get_workflow(workflow_id: str, service: WorkflowServiceDependency) -> dict:
    return service.get(workflow_id)


@router.post(
    "/{workflow_id}/clarifications", response_model=WorkflowResponse, response_model_by_alias=True
)
def submit_clarification(
    workflow_id: str, payload: ClarificationSubmitRequest, service: WorkflowServiceDependency
) -> dict:
    return service.clarify(workflow_id, payload.model_dump(mode="json", by_alias=True))
