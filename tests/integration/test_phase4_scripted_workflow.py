import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.phase3_helpers import approve_pending


def test_phase4_scripted_workflow_is_labeled_platform_test_double(
    app: FastAPI, client: TestClient
) -> None:
    response = client.post(
        "/api/v1/workflows",
        json={
            "scenarioType": "GREENFIELD",
            "requirement": (
                "Build a URL shortening API with short codes, redirects, expiration, and analytics."
            ),
            "workspaceName": "phase4-scripted-target",
            "scriptedScenario": "HAPPY_PATH",
        },
    )
    assert response.status_code == 201, response.text
    workflow = response.json()
    assert workflow["scenarioProfile"]["profile_id"] == "URL_SHORTENER_GREENFIELD"
    workflow = approve_pending(client, workflow)
    workflow = approve_pending(client, workflow)
    assert workflow["status"] == "WAITING_FOR_RELEASE_APPROVAL"
    evidence = client.get(
        f"/api/v1/workflows/{workflow['workflowId']}/artifacts/09-target-contract-evidence.json"
    )
    assert evidence.status_code == 200
    payload = json.loads(evidence.json()["content"])
    assert payload == {
        "profile_id": "URL_SHORTENER_GREENFIELD",
        "reason": "SCRIPTED_PLATFORM_TEST_DOUBLE",
        "status": "NOT_EXECUTED",
    }
    workflow = approve_pending(client, workflow)
    assert workflow["status"] == "READY"
