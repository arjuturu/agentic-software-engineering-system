from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.phase3_helpers import approve_pending, create_workflow


def test_policy_violation_safe_stops_without_writing_env(app: FastAPI, client: TestClient) -> None:
    workflow = create_workflow(client, "POLICY_VIOLATION", "policy-target")
    workflow = approve_pending(client, workflow)
    stopped = approve_pending(client, workflow)
    assert stopped["status"] == "SAFE_STOPPED"
    assert stopped["retryCounts"] == {}
    assert not (
        app.state.workflow_runtime.settings.WORKSPACE_ROOT / "policy-target" / ".env"
    ).exists()
    names = {
        item["fileName"]
        for item in client.get(f"/api/v1/workflows/{stopped['workflowId']}/artifacts").json()
    }
    assert "safe-stop-report.md" in names
    report_path = (
        app.state.workflow_runtime.settings.ARTIFACT_ROOT
        / stopped["workflowId"]
        / "safe-stop-report.md"
    )
    report = report_path.read_text(encoding="utf-8")
    for expected in (
        '"attempted_path": ".env"',
        '"normalized_path": ".env"',
        '"task_id": "TASK-001"',
        '"task_allowed_paths"',
        '"scenario_allowed_paths": []',
        '"effective_allowed_paths"',
        '"policy_rule": "EFFECTIVE_ALLOWED_PATHS"',
    ):
        assert expected in report
    assert str(app.state.workflow_runtime.settings.WORKSPACE_ROOT) not in report
