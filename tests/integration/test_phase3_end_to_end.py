import subprocess

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.phase3_helpers import advance_to_release, approve_pending


def test_phase3_end_to_end(app: FastAPI, client: TestClient) -> None:
    workflow = advance_to_release(client)
    workflow = approve_pending(client, workflow)
    assert workflow["status"] == "READY"
    artifacts = client.get(f"/api/v1/workflows/{workflow['workflowId']}/artifacts")
    audit = client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit")
    assert artifacts.status_code == 200
    assert audit.status_code == 200
    assert any(item["fileName"] == "13-final-engineering-summary.md" for item in artifacts.json())
    events = {item["eventType"] for item in audit.json()}
    required = {"WORKFLOW_CREATED", "CHANGES_APPLIED", "VALIDATION_COMPLETED", "WORKFLOW_COMPLETED"}
    assert required <= events
    target = app.state.workflow_runtime.settings.WORKSPACE_ROOT / "sample-greenfield"
    branch = subprocess.run(
        ["git", "-C", str(target), "branch", "--show-current"],
        check=False,
        capture_output=True,
        text=True,
        shell=False,
        timeout=5,
    )
    remotes = subprocess.run(
        ["git", "-C", str(target), "remote"],
        check=False,
        capture_output=True,
        text=True,
        shell=False,
        timeout=5,
    )
    assert branch.returncode == 0 and branch.stdout.strip().startswith("agent/")
    assert remotes.returncode == 0 and not remotes.stdout.strip()
    assert (target / "sample_app" / "main.py").is_file()
