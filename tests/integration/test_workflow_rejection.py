from fastapi.testclient import TestClient

from tests.phase3_helpers import approve_pending, create_workflow


def test_requirement_rejection_safe_stops(client: TestClient) -> None:
    stopped = approve_pending(
        client, create_workflow(client, workspace="rejected-target"), "REJECT"
    )
    assert stopped["status"] == "SAFE_STOPPED"
