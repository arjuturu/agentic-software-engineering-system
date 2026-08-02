from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.phase3_helpers import advance_to_release


def test_parallel_validation_and_documentation_join(app: FastAPI, client: TestClient) -> None:
    workflow = advance_to_release(client, workspace="parallel-target")
    state = app.state.workflow_runtime.graph.get_state(
        {"configurable": {"thread_id": workflow["threadId"]}}
    ).values
    assert state["validation_branch_complete"] is True
    assert state["documentation_branch_complete"] is True
    assert state["parallel_join_complete"] is True
    assert state["documentation_draft"]["tests_verified"] is False
    assert state["release_package"]["recommended_status"] == "READY"
