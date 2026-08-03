from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.integration.scripted_workflow_helpers import (
    ALIAS_ANSWERS,
    AMBIGUOUS_ALIAS_REQUIREMENT,
    BROWNFIELD_REQUIREMENT,
    create_scripted_workflow,
    drive_greenfield_ready,
    drive_source_workflow_ready,
    git_output,
    snapshot_workspace,
    submit_clarification,
)


def _assert_validation_passed(client: TestClient, workflow: dict) -> None:
    audit = client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
    completed = [item for item in audit if item["eventType"] == "VALIDATION_COMPLETED"]
    assert len(completed) == 1
    assert completed[0]["details"]["status"] == "VALIDATION_PASSED"


def _assert_source_identity(
    client: TestClient, workflow: dict, source_workspace: str
) -> None:
    audit = client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
    source_event = next(
        item for item in audit if item["eventType"] == "BROWNFIELD_SOURCE_VALIDATED"
    )
    assert source_event["details"]["source_workspace"] == source_workspace


def test_all_three_url_shortener_scenarios_share_one_greenfield_baseline(
    app: FastAPI, client: TestClient
) -> None:
    green_name = "three-scenario-green"
    brown_name = "three-scenario-brown"
    alias_name = "three-scenario-alias"
    green = drive_greenfield_ready(client, green_name)
    assert green["status"] == "READY"
    workspace_root = app.state.workflow_runtime.settings.WORKSPACE_ROOT
    source = workspace_root / green_name
    source_before = snapshot_workspace(source)
    source_status_before = git_output(source, "status", "--porcelain")

    brown = create_scripted_workflow(
        client,
        scenario_type="BROWNFIELD",
        workspace=brown_name,
        source=green_name,
        scripted_scenario="URL_SHORTENER_BROWNFIELD_ANALYTICS",
        requirement=BROWNFIELD_REQUIREMENT,
    )
    brown = drive_source_workflow_ready(client, brown)
    assert brown["status"] == "READY"
    assert snapshot_workspace(source) == source_before
    assert git_output(source, "status", "--porcelain") == source_status_before

    alias = create_scripted_workflow(
        client,
        scenario_type="AMBIGUOUS",
        workspace=alias_name,
        source=green_name,
        scripted_scenario="URL_SHORTENER_AMBIGUOUS_ALIASES",
        requirement=AMBIGUOUS_ALIAS_REQUIREMENT,
    )
    assert alias["status"] == "WAITING_FOR_CLARIFICATION"
    alias = submit_clarification(client, alias, ALIAS_ANSWERS)
    alias = drive_source_workflow_ready(client, alias)
    assert alias["status"] == "READY"

    assert brown_name != alias_name
    assert (workspace_root / brown_name).is_dir()
    assert (workspace_root / alias_name).is_dir()
    assert snapshot_workspace(source) == source_before
    assert git_output(source, "status", "--porcelain") == source_status_before
    assert git_output(workspace_root / brown_name, "remote") == ""
    assert git_output(workspace_root / alias_name, "remote") == ""
    _assert_source_identity(client, brown, green_name)
    _assert_source_identity(client, alias, green_name)
    for workflow in (green, brown, alias):
        _assert_validation_passed(client, workflow)
