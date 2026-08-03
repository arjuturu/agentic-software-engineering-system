from fastapi import FastAPI
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


def _brownfield_payload(source: str | None = None) -> dict:
    payload = {
        "scenarioType": "BROWNFIELD",
        "workspaceName": "brownfield-destination",
        "requirement": "Enhance an existing URL shortener with click analytics.",
        "scriptedScenario": "URL_SHORTENER_BROWNFIELD_ANALYTICS",
    }
    if source is not None:
        payload["sourceWorkspace"] = source
    return payload


def test_brownfield_requires_source_workspace(client: TestClient) -> None:
    response = client.post("/api/v1/workflows", json=_brownfield_payload())

    assert response.status_code == 422


def test_brownfield_rejects_unknown_and_unsafe_sources(client: TestClient) -> None:
    missing = client.post(
        "/api/v1/workflows", json=_brownfield_payload("missing-source")
    )
    traversal = client.post(
        "/api/v1/workflows", json=_brownfield_payload("../source")
    )
    absolute = client.post(
        "/api/v1/workflows", json=_brownfield_payload("C:/source")
    )

    assert missing.status_code == 404
    assert traversal.status_code == 400
    assert absolute.status_code == 400


def test_brownfield_rejects_same_or_existing_destination(
    app: FastAPI, client: TestClient
) -> None:
    workspace_root = app.state.workflow_runtime.settings.WORKSPACE_ROOT
    source = workspace_root / "brownfield-source"
    (source / ".git").mkdir(parents=True)
    same = _brownfield_payload("brownfield-source")
    same["workspaceName"] = "brownfield-source"
    existing = workspace_root / "brownfield-destination"
    existing.mkdir()

    same_response = client.post("/api/v1/workflows", json=same)
    existing_response = client.post(
        "/api/v1/workflows", json=_brownfield_payload("brownfield-source")
    )

    assert same_response.status_code == 409
    assert existing_response.status_code == 409
