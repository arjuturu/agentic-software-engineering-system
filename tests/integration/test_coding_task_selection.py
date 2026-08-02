from fastapi.testclient import TestClient

from app.agents.scripted_provider import ScriptedProvider
from tests.phase3_helpers import approve_pending, create_workflow


def test_presatisfied_architecture_task_is_rejected_before_approval(
    client: TestClient, monkeypatch
) -> None:
    original_planning = ScriptedProvider._planning

    def duplicate_governance_plan(payload, scenario, retry_number):
        plan = original_planning(payload, scenario, retry_number)
        duplicate = {
            **plan["tasks"][0],
            "task_id": "TASK-000",
            "title": "Generate architecture design artifact",
            "description": "Create architecture and implementation plan Markdown artifacts.",
            "expected_files": ["architecture_plan.md"],
            "allowed_paths": ["architecture_plan.md"],
        }
        return {
            **plan,
            "tasks": [duplicate, *plan["tasks"]],
            "execution_order": ["TASK-000", *plan["execution_order"]],
            "critical_path": ["TASK-000", *plan["critical_path"]],
        }

    monkeypatch.setattr(
        ScriptedProvider, "_planning", staticmethod(duplicate_governance_plan)
    )
    workflow = create_workflow(client, workspace="duplicate-governance-plan")

    stopped = approve_pending(client, workflow)

    assert stopped["status"] == "SAFE_STOPPED"
    audit = client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
    failures = [item for item in audit if item["eventType"] == "PLAN_VALIDATION_FAILED"]
    assert len(failures) == 3
    assert all(
        "DUPLICATE_UPSTREAM_ARTIFACT_TASK"
        in {error["code"] for error in item["details"]["validation_errors"]}
        for item in failures
    )
    assert not any(item["eventType"] == "TASK_SATISFIED" for item in audit)
    assert not any(item["eventType"] == "CODING_TASK_SELECTED" for item in audit)


def test_setup_task_is_selected_before_dependent_implementation(
    client: TestClient, monkeypatch
) -> None:
    original_planning = ScriptedProvider._planning

    def setup_first_plan(payload, scenario, retry_number):
        return original_planning(payload, scenario, retry_number)

    monkeypatch.setattr(ScriptedProvider, "_planning", staticmethod(setup_first_plan))
    workflow = create_workflow(client, workspace="setup-task-first")
    workflow = approve_pending(client, workflow)
    result = approve_pending(client, workflow)

    assert result["status"] == "WAITING_FOR_RELEASE_APPROVAL"
    audit = client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
    selected = [item for item in audit if item["eventType"] == "CODING_TASK_SELECTED"]
    assert selected[0]["details"] == {
        "task_id": "TASK-001",
        "task_type": "SETUP",
        "dependency_status": "READY",
        "dependencies": [],
        "incomplete_dependencies": [],
        "originating_task_id": None,
        "retry_task_id": None,
    }
    assert [item["details"]["task_id"] for item in selected] == [
        "TASK-001",
        "TASK-002",
        "TASK-003",
        "TASK-004",
        "TASK-005",
    ]
    completed = [item for item in audit if item["eventType"] == "TASK_COMPLETED"]
    assert [item["details"]["task_id"] for item in completed] == [
        "TASK-001",
        "TASK-002",
        "TASK-003",
        "TASK-004",
        "TASK-005",
    ]
    event_types = [item["eventType"] for item in audit]
    assert event_types.index("VALIDATION_STARTED") > max(
        index for index, value in enumerate(event_types) if value == "TASK_COMPLETED"
    )


def test_unknown_dependency_is_rejected_during_plan_validation(
    client: TestClient, monkeypatch
) -> None:
    original_planning = ScriptedProvider._planning

    def blocked_plan(payload, scenario, retry_number):
        plan = original_planning(payload, scenario, retry_number)
        blocked = {
            **plan["tasks"][0],
            "task_type": "setup",
            "dependencies": ["TASK-999"],
        }
        return {**plan, "tasks": [blocked, *plan["tasks"][1:]]}

    monkeypatch.setattr(ScriptedProvider, "_planning", staticmethod(blocked_plan))
    workflow = create_workflow(client, workspace="dependency-deadlock")
    stopped = approve_pending(client, workflow)

    assert stopped["status"] == "SAFE_STOPPED"
    audit = client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
    failures = [item for item in audit if item["eventType"] == "PLAN_VALIDATION_FAILED"]
    assert len(failures) == 3
    assert all(
        "DEPENDENCY_REFERENCE_INVALID"
        in {error["code"] for error in item["details"]["validation_errors"]}
        for item in failures
    )
    assert not any(item["eventType"] == "CODING_TASK_SELECTED" for item in audit)
