from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agents.scripted_provider import ScriptedProvider
from app.database.models import WorkflowTask
from app.tools.controlled_editor import ControlledEditor
from app.tools.models import CommandResult, ToolStatus, ValidationSuiteResult
from app.tools.test_runner import TestRunner
from tests.phase3_helpers import approve_pending, create_workflow


def test_architecture_approval_skips_completed_design_task_and_passes_task_paths(
    app: FastAPI, client: TestClient, monkeypatch
) -> None:
    original_planning = ScriptedProvider._planning
    original_apply_batch = ControlledEditor.apply_batch
    editor_allowed_paths: list[list[str]] = []

    def design_first_plan(payload, scenario, retry_number):
        plan = original_planning(payload, scenario, retry_number)
        implementation = {**plan["tasks"][0]}
        implementation.update(
            {
                "task_id": "TASK-002",
                "dependencies": ["TASK-001"],
                "entry_criteria": ["Architecture and implementation plan approved"],
            }
        )
        validation = {**plan["tasks"][1]}
        validation.update({"task_id": "TASK-003", "dependencies": ["TASK-002"]})
        design = {
            "task_id": "TASK-001",
            "title": "Design Architecture and Implementation Plan",
            "description": "Produce and approve architecture and planning artifacts.",
            "task_type": "Design",
            "dependencies": [],
            "parallel_group": None,
            "risk_level": "LOW",
            "expected_files": ["architecture_plan.txt"],
            "allowed_paths": ["/architecture_plan.txt"],
            "entry_criteria": [],
            "exit_criteria": ["Architecture and implementation plan approved"],
            "validation_commands": ["TARGET_IMPORT_CHECK"],
            "acceptance_criteria_covered": [
                "Provide an architecture design and implementation plan before coding."
            ],
        }
        return {
            **plan,
            "tasks": [design, implementation, validation],
            "execution_order": ["TASK-001", "TASK-002", "TASK-003"],
            "critical_path": ["TASK-001", "TASK-002", "TASK-003"],
        }

    def track_apply_batch(self, workspace, edits, **kwargs):
        allowed_paths = kwargs.get("allowed_paths")
        if allowed_paths is not None:
            editor_allowed_paths.append(list(allowed_paths))
        return original_apply_batch(self, workspace, edits, **kwargs)

    def passing_validation(self, repository):
        del self, repository
        command = CommandResult(
            command_id="PYTEST",
            status=ToolStatus.SUCCESS,
            exit_code=0,
            stdout="passed",
            stderr="",
            duration_ms=1,
        )
        return ValidationSuiteResult(
            status=ToolStatus.SUCCESS,
            ruff=command.model_copy(update={"command_id": "RUFF_CHECK"}),
            pytest=command,
        )

    monkeypatch.setattr(ScriptedProvider, "_planning", staticmethod(design_first_plan))
    monkeypatch.setattr(TestRunner, "run_validation_suite", passing_validation)
    monkeypatch.setattr(ControlledEditor, "apply_batch", track_apply_batch)

    workflow = create_workflow(client, workspace="design-task-skip")
    architecture_pending = approve_pending(client, workflow)
    result = approve_pending(client, architecture_pending)

    audit = client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
    assert result["status"] == "WAITING_FOR_RELEASE_APPROVAL", (result, audit)
    checkpoint = app.state.workflow_runtime.graph.get_state(
        {"configurable": {"thread_id": workflow["threadId"]}}
    ).values
    tasks = checkpoint["implementation_plan"]["tasks"]
    assert [task["task_id"] for task in tasks] == ["TASK-001", "TASK-002", "TASK-003"]
    assert tasks[0]["status"] == "COMPLETED"
    assert checkpoint["active_task"]["task_id"] == "TASK-002"

    with app.state.workflow_runtime.sessions() as session:
        stored_tasks = list(
            session.scalars(
                select(WorkflowTask)
                .where(WorkflowTask.workflow_id == workflow["workflowId"])
                .order_by(WorkflowTask.task_key)
            )
        )
    assert [(task.task_key, task.status) for task in stored_tasks] == [
        ("TASK-001", "COMPLETED"),
        ("TASK-002", "PLANNED"),
        ("TASK-003", "PLANNED"),
    ]

    audit = client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
    satisfied = [item for item in audit if item["eventType"] == "TASK_SATISFIED"]
    selected = [item for item in audit if item["eventType"] == "CODING_TASK_SELECTED"]
    change_plan = [item for item in audit if item["eventType"] == "CHANGE_PLAN_CREATED"]
    assert len(satisfied) == 1
    assert satisfied[0]["details"]["task_id"] == "TASK-001"
    assert len(selected) == 1
    assert selected[0]["details"] == {
        "task_id": "TASK-002",
        "task_type": "IMPLEMENTATION",
        "dependency_status": "READY",
        "dependencies": ["TASK-001"],
        "incomplete_dependencies": [],
    }
    assert change_plan[0]["details"]["task_id"] == "TASK-002"
    assert editor_allowed_paths == [["pyproject.toml", "sample_app", "tests"]]
    repository = app.state.workflow_runtime.settings.WORKSPACE_ROOT / "design-task-skip"
    assert not (repository / "architecture_plan.txt").exists()

def test_setup_task_is_selected_before_dependent_implementation(
    client: TestClient, monkeypatch
) -> None:
    original_planning = ScriptedProvider._planning

    def setup_first_plan(payload, scenario, retry_number):
        plan = original_planning(payload, scenario, retry_number)
        setup = {**plan["tasks"][0], "task_type": "setup"}
        implementation = {
            **plan["tasks"][1],
            "task_type": "implementation",
            "dependencies": ["TASK-001"],
        }
        return {**plan, "tasks": [setup, implementation]}

    monkeypatch.setattr(ScriptedProvider, "_planning", staticmethod(setup_first_plan))
    workflow = create_workflow(client, workspace="setup-task-first")
    workflow = approve_pending(client, workflow)
    result = approve_pending(client, workflow)

    assert result["status"] == "WAITING_FOR_RELEASE_APPROVAL"
    audit = client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
    selected = [item for item in audit if item["eventType"] == "CODING_TASK_SELECTED"]
    assert selected[0]["details"] == {
        "task_id": "TASK-001",
        "task_type": "setup",
        "dependency_status": "READY",
        "dependencies": [],
        "incomplete_dependencies": [],
    }


def test_dependency_deadlock_safe_stops_with_explicit_error(
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
        return {
            **plan,
            "tasks": [blocked],
            "execution_order": ["TASK-001"],
            "critical_path": ["TASK-001"],
        }

    monkeypatch.setattr(ScriptedProvider, "_planning", staticmethod(blocked_plan))
    workflow = create_workflow(client, workspace="dependency-deadlock")
    workflow = approve_pending(client, workflow)
    stopped = approve_pending(client, workflow)

    assert stopped["status"] == "SAFE_STOPPED"
    audit = client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
    safe_stop = [item for item in audit if item["eventType"] == "SAFE_STOP_TRIGGERED"]
    assert safe_stop[0]["details"]["error_code"] == "TASK_DEPENDENCY_VIOLATION"
    assert not any(item["eventType"] == "CODING_TASK_SELECTED" for item in audit)
