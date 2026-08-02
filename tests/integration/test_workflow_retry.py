from fastapi.testclient import TestClient

from tests.phase3_helpers import advance_to_release


def test_coding_retry_then_pass(client: TestClient) -> None:
    workflow = advance_to_release(client, "CODING_RETRY_THEN_PASS", "retry-target")
    assert workflow["retryCounts"]["coding"] == 1
    events = [
        item["eventType"]
        for item in client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
    ]
    assert "RETRY_STARTED" in events
    assert events.count("VALIDATION_COMPLETED") == 2
