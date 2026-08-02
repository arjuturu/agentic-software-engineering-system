from fastapi.testclient import TestClient

from tests.phase3_helpers import approve_pending, create_workflow


def test_architecture_change_request_replans_and_requires_approval(client: TestClient) -> None:
    workflow = approve_pending(client, create_workflow(client, workspace="architecture-change"))
    assert workflow["architectureVersion"] == 1
    changed = approve_pending(client, workflow, "REQUEST_CHANGES")
    assert changed["status"] == "WAITING_FOR_ARCHITECTURE_APPROVAL"
    assert changed["architectureVersion"] == 2
    names = {
        item["fileName"]
        for item in client.get(f"/api/v1/workflows/{workflow['workflowId']}/artifacts").json()
    }
    assert "04-architecture-design-v2.md" in names
    assert "05-implementation-plan-v2.md" in names
