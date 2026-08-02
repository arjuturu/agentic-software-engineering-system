from fastapi.testclient import TestClient

from tests.phase3_helpers import create_workflow


def test_workflow_creation_pauses_for_requirement_approval(client: TestClient) -> None:
    workflow = create_workflow(client)
    assert workflow["status"] == "WAITING_FOR_REQUIREMENT_APPROVAL"
    assert workflow["currentStage"] == "REQUIREMENT_APPROVAL"
    assert workflow["threadId"].startswith("TH-")
    assert workflow["workflowId"].startswith("WF-")
    assert workflow["pendingApproval"]["gateType"] == "REQUIREMENT"


def test_openapi_contains_phase3_routes(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    required = {
        "/api/v1/workflows",
        "/api/v1/workflows/{workflow_id}",
        "/api/v1/workflows/{workflow_id}/clarifications",
        "/api/v1/workflows/{workflow_id}/approvals/{approval_id}",
        "/api/v1/workflows/{workflow_id}/artifacts",
        "/api/v1/workflows/{workflow_id}/audit",
    }
    assert required <= set(paths)
