from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.phase3_helpers import approve_pending, create_workflow


def test_nonrecoverable_validation_failure_rolls_back(app: FastAPI, client: TestClient) -> None:
    workflow = create_workflow(client, "ROLLBACK_REQUIRED", "rollback-target")
    workflow = approve_pending(client, workflow)
    result = approve_pending(client, workflow)
    assert result["status"] == "NOT_READY"
    target = app.state.workflow_runtime.settings.WORKSPACE_ROOT / "rollback-target"
    assert not (target / "sample_app" / "main.py").exists()
    names = {
        item["fileName"]
        for item in client.get(f"/api/v1/workflows/{result['workflowId']}/artifacts").json()
    }
    assert "rollback-report.md" in names
