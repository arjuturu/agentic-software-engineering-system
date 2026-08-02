from fastapi.testclient import TestClient

from tests.phase3_helpers import approve_pending, create_workflow


def test_requirement_approval_validates_version_and_is_idempotent(client: TestClient) -> None:
    workflow = create_workflow(client, workspace="requirement-approval")
    pending = workflow["pendingApproval"]
    invalid = client.post(
        f"/api/v1/workflows/{workflow['workflowId']}/approvals/{pending['approvalId']}",
        json={
            "gateType": "REQUIREMENT",
            "stateVersion": pending["stateVersion"] + 1,
            "action": "APPROVE",
            "decidedBy": "test-user",
        },
    )
    assert invalid.status_code == 409
    next_state = approve_pending(client, workflow)
    assert next_state["status"] == "WAITING_FOR_ARCHITECTURE_APPROVAL"
    duplicate = client.post(
        f"/api/v1/workflows/{workflow['workflowId']}/approvals/{pending['approvalId']}",
        json={
            "gateType": "REQUIREMENT",
            "stateVersion": pending["stateVersion"],
            "action": "APPROVE",
            "decidedBy": "test-user",
        },
    )
    assert duplicate.status_code == 409
