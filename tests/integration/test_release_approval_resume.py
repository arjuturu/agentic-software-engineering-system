from fastapi.testclient import TestClient

from tests.phase3_helpers import advance_to_release, approve_pending


def test_release_approval_with_conditions(client: TestClient) -> None:
    workflow = advance_to_release(client, workspace="conditional-release")
    completed = approve_pending(client, workflow, "APPROVE_WITH_CONDITIONS")
    assert completed["status"] == "READY_WITH_CONDITIONS"
