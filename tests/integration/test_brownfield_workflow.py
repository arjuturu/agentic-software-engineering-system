from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.scripted_provider import ScriptedProvider
from tests.integration.scripted_workflow_helpers import (
    BROWNFIELD_REQUIREMENT,
    GREENFIELD_REQUIREMENT,
    create_scripted_workflow,
    git_output,
    snapshot_workspace,
)
from tests.phase3_helpers import approve_pending


def test_scripted_greenfield_then_brownfield_reaches_ready(
    app: FastAPI, client: TestClient, monkeypatch
) -> None:
    captured: list[tuple[str, str, dict]] = []
    original_generate = ScriptedProvider.generate

    def capture(self: ScriptedProvider, **kwargs):
        payload = kwargs["input_payload"]
        captured.append((payload.get("scenario_type", ""), kwargs["agent_name"], payload))
        return original_generate(self, **kwargs)

    monkeypatch.setattr(ScriptedProvider, "generate", capture)
    green = create_scripted_workflow(
        client,
        scenario_type="GREENFIELD",
        workspace="scripted-url-green",
        scripted_scenario="URL_SHORTENER_GREENFIELD_HAPPY_PATH",
        requirement=GREENFIELD_REQUIREMENT,
    )
    green = approve_pending(client, green)
    assert green["currentStage"] == "ARCHITECTURE_APPROVAL"
    green = approve_pending(client, green)
    assert green["currentStage"] == "RELEASE_APPROVAL"
    green = approve_pending(client, green)
    assert green["status"] == "READY"

    workspace_root = app.state.workflow_runtime.settings.WORKSPACE_ROOT
    source = workspace_root / "scripted-url-green"
    source_before = snapshot_workspace(source)
    source_status_before = git_output(source, "status", "--porcelain")

    brown = create_scripted_workflow(
        client,
        scenario_type="BROWNFIELD",
        workspace="scripted-url-brown",
        source="scripted-url-green",
        scripted_scenario="URL_SHORTENER_BROWNFIELD_ANALYTICS",
        requirement=BROWNFIELD_REQUIREMENT,
    )
    brown = approve_pending(client, brown)
    assert brown["currentStage"] == "ARCHITECTURE_APPROVAL"
    destination = workspace_root / "scripted-url-brown"
    assert not (destination / "url_shortener.db").is_file()
    brown_audit = client.get(
        f"/api/v1/workflows/{brown['workflowId']}/audit"
    ).json()
    event_types = [item["eventType"] for item in brown_audit]
    assert event_types.index("BROWNFIELD_SOURCE_VALIDATED") < event_types.index(
        "BROWNFIELD_WORKSPACE_COPIED"
    )
    repository_started = next(
        index
        for index, item in enumerate(brown_audit)
        if item["eventType"] == "AGENT_STARTED" and item["stage"] == "REPOSITORY_ANALYSIS"
    )
    design_started = next(
        index
        for index, item in enumerate(brown_audit)
        if item["eventType"] == "AGENT_STARTED" and item["stage"] == "DESIGN"
    )
    planning_started = next(
        index
        for index, item in enumerate(brown_audit)
        if item["eventType"] == "AGENT_STARTED" and item["stage"] == "PLANNING"
    )
    assert repository_started < design_started < planning_started

    brown = approve_pending(client, brown)
    assert brown["currentStage"] == "RELEASE_APPROVAL"
    brown = approve_pending(client, brown)
    assert brown["status"] == "READY"

    assert snapshot_workspace(source) == source_before
    assert git_output(source, "status", "--porcelain") == source_status_before
    assert git_output(destination, "remote") == ""
    assert (destination / "alembic" / "versions" / "0002_add_click_count.py").is_file()

    brown_design = next(
        payload
        for scenario, agent, payload in captured
        if scenario == "BROWNFIELD" and agent == "DESIGN_AGENT"
    )
    brown_plan = next(
        payload
        for scenario, agent, payload in captured
        if scenario == "BROWNFIELD" and agent == "PLANNING_AGENT"
    )
    brown_coding = [
        payload
        for scenario, agent, payload in captured
        if scenario == "BROWNFIELD" and agent == "CODING_AGENT"
    ]
    assert brown_design["repository_analysis"]["status"] == "ANALYSIS_COMPLETE"
    assert brown_plan["repository_analysis"]["status"] == "ANALYSIS_COMPLETE"
    assert "app/models.py" in brown_design["repository_analysis"]["impacted_files"]
    assert "tests/test_api.py" in brown_plan["repository_analysis"]["existing_tests"]
    assert brown_design["repository_scan"]["source_workspace"] == "scripted-url-green"
    assert brown_plan["repository_scan"]["destination_workspace"] == "scripted-url-brown"
    modify_payload = next(
        payload
        for payload in brown_coding
        if payload["active_task"]["task_id"] == "TASK-002"
    )
    model_context = next(
        item
        for item in modify_payload["repository_context"]
        if item["relative_path"] == "app/models.py"
    )
    assert model_context["content"]
    assert model_context["sha256"] == modify_payload["file_hashes"]["app/models.py"]

    final_audit = client.get(
        f"/api/v1/workflows/{brown['workflowId']}/audit"
    ).json()
    final_events = [item["eventType"] for item in final_audit]
    for event in (
        "BROWNFIELD_SOURCE_VALIDATED",
        "BROWNFIELD_WORKSPACE_COPIED",
        "BROWNFIELD_BASELINE_CREATED",
        "BROWNFIELD_BRANCH_CREATED",
        "CHANGES_APPLIED",
        "VALIDATION_COMPLETED",
        "WORKFLOW_COMPLETED",
    ):
        assert event in final_events
