import os
import subprocess
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.scripted_provider import ScriptedProvider
from app.database.models import WorkflowRequirement
from tests.integration.scripted_workflow_helpers import (
    ALIAS_ANSWERS,
    AMBIGUOUS_ALIAS_REQUIREMENT,
    create_scripted_workflow,
    drive_greenfield_ready,
    git_output,
    snapshot_workspace,
    submit_clarification,
)
from tests.phase3_helpers import approve_pending

EXPECTED_QUESTIONS = [f"Q-ALIAS-{number:03d}" for number in range(1, 7)]

TARGET_API_PROBE = """
from fastapi.testclient import TestClient

from app.main import app

with TestClient(app) as client:
    generated = client.post(
        "/api/v1/urls",
        json={"original_url": "https://generated.example"},
    )
    assert generated.status_code == 201
    generated_code = generated.json()["short_code"]
    assert len(generated_code) == 8 and generated_code.isalnum()
    generated_redirect = client.get(f"/{generated_code}", follow_redirects=False)
    assert generated_redirect.status_code == 307
    assert generated_redirect.headers["location"] == "https://generated.example"

    alias = client.post(
        "/api/v1/urls",
        json={
            "original_url": "https://example.com",
            "custom_alias": "  My-Alias  ",
        },
    )
    assert alias.status_code == 201
    assert alias.json() == {
        "original_url": "https://example.com",
        "short_code": "my-alias",
        "short_url": "http://testserver/my-alias",
    }
    alias_redirect = client.get("/my-alias", follow_redirects=False)
    assert alias_redirect.status_code == 307
    assert alias_redirect.headers["location"] == "https://example.com"

    duplicate = client.post(
        "/api/v1/urls",
        json={
            "original_url": "https://duplicate.example",
            "custom_alias": "MY-ALIAS",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "Custom alias already exists"}

    namespace_conflict = client.post(
        "/api/v1/urls",
        json={
            "original_url": "https://namespace.example",
            "custom_alias": generated_code.upper(),
        },
    )
    assert namespace_conflict.status_code == 409
    assert namespace_conflict.json() == {"detail": "Custom alias already exists"}

    for invalid in (
        "abc",
        "a" * 31,
        "bad alias",
        "bad.alias",
        "api",
        "docs",
        "openapi.json",
        "health",
    ):
        rejected = client.post(
            "/api/v1/urls",
            json={
                "original_url": "https://invalid.example",
                "custom_alias": invalid,
            },
        )
        assert rejected.status_code == 422

    missing = client.get("/unknown-code", follow_redirects=False)
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Short URL not found"}
"""


def _run_target_probe(repository) -> None:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-c", TARGET_API_PROBE],
        cwd=repository,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        shell=False,
        timeout=30,
    )
    assert result.returncode == 0, {
        "stdout": result.stdout[-2000:],
        "stderr": result.stderr[-2000:],
    }


def test_ambiguous_alias_workflow_clarifies_and_reaches_ready(
    app: FastAPI, client: TestClient, monkeypatch
) -> None:
    captured: list[tuple[str, str, dict, dict]] = []
    original_generate = ScriptedProvider.generate

    def capture(self: ScriptedProvider, **kwargs):
        payload = kwargs["input_payload"]
        result = original_generate(self, **kwargs)
        captured.append(
            (
                payload.get("scripted_scenario", ""),
                kwargs["agent_name"],
                payload,
                result.model_dump(mode="json"),
            )
        )
        return result

    monkeypatch.setattr(ScriptedProvider, "generate", capture)
    green = drive_greenfield_ready(client, "alias-greenfield-source")
    assert green["status"] == "READY"
    workspace_root = app.state.workflow_runtime.settings.WORKSPACE_ROOT
    source = workspace_root / "alias-greenfield-source"
    source_before = snapshot_workspace(source)
    source_status_before = git_output(source, "status", "--porcelain")
    source_migrations = {
        item.name for item in (source / "alembic" / "versions").glob("*.py")
    }

    workflow = create_scripted_workflow(
        client,
        scenario_type="AMBIGUOUS",
        workspace="alias-ambiguous-destination",
        source="alias-greenfield-source",
        scripted_scenario="URL_SHORTENER_AMBIGUOUS_ALIASES",
        requirement=AMBIGUOUS_ALIAS_REQUIREMENT,
    )

    assert workflow["status"] == "WAITING_FOR_CLARIFICATION"
    assert workflow["currentStage"] == "CLARIFICATION"
    questions = workflow["pendingInteraction"]["payload"]["questions"]
    assert [item["question_id"] for item in questions] == EXPECTED_QUESTIONS
    pre_clarification_audit = client.get(
        f"/api/v1/workflows/{workflow['workflowId']}/audit"
    ).json()
    assert not any(
        item["eventType"] in {"CHANGES_APPLIED", "BROWNFIELD_WORKSPACE_COPIED"}
        or (
            item["eventType"] == "AGENT_STARTED"
            and item["stage"] in {"REPOSITORY_ANALYSIS", "DESIGN", "PLANNING", "CODING"}
        )
        for item in pre_clarification_audit
    )
    assert not (workspace_root / "alias-ambiguous-destination").exists()

    workflow = submit_clarification(client, workflow, ALIAS_ANSWERS)
    assert workflow["status"] == "WAITING_FOR_REQUIREMENT_APPROVAL"
    with app.state.workflow_runtime.sessions() as session:
        requirement = (
            session.query(WorkflowRequirement)
            .filter_by(workflow_id=workflow["workflowId"], version=1)
            .one()
        )
        lineage = requirement.analysis_json["pending_clarification"]
        assert [item["question_id"] for item in lineage["questions"]] == EXPECTED_QUESTIONS
        assert {
            item["question_id"]: item["answer"] for item in lineage["answers"]
        } == ALIAS_ANSWERS

    workflow = approve_pending(client, workflow)
    approval_audit = client.get(
        f"/api/v1/workflows/{workflow['workflowId']}/audit"
    ).json()
    diagnostics = [
        (item["eventType"], item["stage"], item.get("details", {}))
        for item in approval_audit
        if item["eventType"] in {"AGENT_FAILED", "PLAN_VALIDATION_FAILED", "SAFE_STOPPED"}
    ]
    assert workflow["currentStage"] == "ARCHITECTURE_APPROVAL", diagnostics
    destination = workspace_root / "alias-ambiguous-destination"
    assert destination.is_dir()
    audit = client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
    repository_started = next(
        index
        for index, item in enumerate(audit)
        if item["eventType"] == "AGENT_STARTED" and item["stage"] == "REPOSITORY_ANALYSIS"
    )
    design_started = next(
        index
        for index, item in enumerate(audit)
        if item["eventType"] == "AGENT_STARTED" and item["stage"] == "DESIGN"
    )
    planning_started = next(
        index
        for index, item in enumerate(audit)
        if item["eventType"] == "AGENT_STARTED" and item["stage"] == "PLANNING"
    )
    assert repository_started < design_started < planning_started

    alias_captures = [
        item
        for item in captured
        if item[0] == "URL_SHORTENER_AMBIGUOUS_ALIASES"
    ]
    design_payload = next(item[2] for item in alias_captures if item[1] == "DESIGN_AGENT")
    planning_payload = next(
        item[2] for item in alias_captures if item[1] == "PLANNING_AGENT"
    )
    plan_output = next(item[3] for item in alias_captures if item[1] == "PLANNING_AGENT")
    assert design_payload["repository_analysis"]["status"] == "ANALYSIS_COMPLETE"
    assert planning_payload["repository_analysis"]["status"] == "ANALYSIS_COMPLETE"
    assert "app/schemas.py" in design_payload["repository_analysis"]["impacted_files"]
    assert design_payload["repository_scan"]["source_workspace"] == "alias-greenfield-source"
    assert (
        planning_payload["repository_scan"]["destination_workspace"]
        == "alias-ambiguous-destination"
    )
    assert all(task["task_type"] != "MIGRATION" for task in plan_output["tasks"])
    assert plan_output["execution_order"] == [
        f"TASK-{number:03d}" for number in range(1, 8)
    ]

    workflow = approve_pending(client, workflow)
    assert workflow["currentStage"] == "RELEASE_APPROVAL"
    coding_captures = [
        item
        for item in captured
        if item[0] == "URL_SHORTENER_AMBIGUOUS_ALIASES"
        and item[1] == "CODING_AGENT"
    ]
    assert coding_captures
    for _, _, payload, output in coding_captures:
        for edit in output["structured_edits"]:
            assert edit["operation"] == "MODIFY"
            assert edit["expected_hash"] == payload["file_hashes"][edit["relative_path"]]
            assert edit["content"] is not None
            assert edit["old_text"] is None
            assert edit["replacement_text"] is None

    destination_migrations = {
        item.name for item in (destination / "alembic" / "versions").glob("*.py")
    }
    assert destination_migrations == source_migrations
    _run_target_probe(destination)
    assert git_output(destination, "remote") == ""

    workflow = approve_pending(client, workflow)
    assert workflow["status"] == "READY"
    assert snapshot_workspace(source) == source_before
    assert git_output(source, "status", "--porcelain") == source_status_before

    final_audit = client.get(
        f"/api/v1/workflows/{workflow['workflowId']}/audit"
    ).json()
    event_types = [item["eventType"] for item in final_audit]
    assert event_types.count("CLARIFICATION_REQUESTED") == 1
    assert event_types.count("CLARIFICATION_SUBMITTED") == 1
    for expected in (
        "BROWNFIELD_SOURCE_VALIDATED",
        "BROWNFIELD_WORKSPACE_COPIED",
        "CHANGES_APPLIED",
        "VALIDATION_COMPLETED",
        "WORKFLOW_COMPLETED",
    ):
        assert expected in event_types
