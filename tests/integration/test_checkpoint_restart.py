from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.phase3_helpers import approve_pending, create_workflow


def test_file_checkpoint_survives_runtime_restart(app: FastAPI) -> None:
    with TestClient(app) as first:
        workflow = create_workflow(first, workspace="restart-target")
        thread_id = workflow["threadId"]
    with TestClient(app) as second:
        resumed = approve_pending(second, workflow)
        assert resumed["threadId"] == thread_id
        assert resumed["status"] == "WAITING_FOR_ARCHITECTURE_APPROVAL"
