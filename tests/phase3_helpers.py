from fastapi.testclient import TestClient


def create_workflow(
    client: TestClient, scenario: str = "HAPPY_PATH", workspace: str = "sample-greenfield"
) -> dict:
    response = client.post(
        "/api/v1/workflows",
        json={
            "scenarioType": "GREENFIELD",
            "requirement": "Create a small Python service with tests.",
            "workspaceName": workspace,
            "scriptedScenario": scenario,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def approve_pending(client: TestClient, workflow: dict, action: str = "APPROVE") -> dict:
    pending = workflow["pendingApproval"]
    response = client.post(
        f"/api/v1/workflows/{workflow['workflowId']}/approvals/{pending['approvalId']}",
        json={
            "gateType": pending["gateType"],
            "stateVersion": pending["stateVersion"],
            "action": action,
            "comments": "Governed test decision",
            "conditions": ["Observe locally"] if action == "APPROVE_WITH_CONDITIONS" else [],
            "decidedBy": "test-user",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def advance_to_release(
    client: TestClient, scenario: str = "HAPPY_PATH", workspace: str = "sample-greenfield"
) -> dict:
    workflow = create_workflow(client, scenario, workspace)
    workflow = approve_pending(client, workflow)
    workflow = approve_pending(client, workflow)
    audit = client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
    assert workflow["status"] == "WAITING_FOR_RELEASE_APPROVAL", (workflow, audit)
    return workflow
