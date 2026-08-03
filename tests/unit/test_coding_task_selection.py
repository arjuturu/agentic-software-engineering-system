import pytest

from app.orchestration.tasks import (
    all_required_tasks_completed,
    dependency_status,
    executable_plan,
    first_executable_task,
    mark_task_completed,
    satisfy_approved_design_tasks,
)
from app.schemas.agents.planning import PlanTaskType


def _task(
    task_id: str,
    task_type: str,
    *,
    dependencies: list[str] | None = None,
    status: str = "PLANNED",
) -> dict:
    return {
        "task_id": task_id,
        "title": f"{task_type} task",
        "task_type": task_type,
        "dependencies": dependencies or [],
        "status": status,
        "acceptance_criteria_covered": ["Task output is complete"],
        "exit_criteria": ["Task completed"],
    }


def _design_task() -> dict:
    task = _task("TASK-000", "Design")
    task["acceptance_criteria_covered"] = [
        "Provide an architecture design and implementation plan before coding."
    ]
    task["exit_criteria"] = ["Architecture and implementation plan approved"]
    return task


def test_setup_task_is_selected_before_dependent_implementation() -> None:
    plan = {
        "tasks": [
            _task("TASK-001", "SETUP"),
            _task("TASK-002", "IMPLEMENTATION", dependencies=["TASK-001"]),
        ],
        "execution_order": ["TASK-001", "TASK-002"],
    }

    selected = first_executable_task(plan)

    assert selected is not None
    assert selected["task_id"] == "TASK-001"
    assert selected["task_type"] == "SETUP"
    assert dependency_status(plan, selected)["status"] == "READY"


def test_completed_design_task_is_preserved_and_skipped() -> None:
    plan = {
        "tasks": [_design_task(), _task("TASK-001", "SETUP")],
        "execution_order": ["TASK-000", "TASK-001"],
    }

    approved, satisfied = satisfy_approved_design_tasks(plan)
    selected = first_executable_task(approved)

    assert satisfied == ["TASK-000"]
    assert approved["tasks"][0]["status"] == "COMPLETED"
    assert selected is not None
    assert selected["task_id"] == "TASK-001"
    assert [task["task_id"] for task in approved["tasks"]] == ["TASK-000", "TASK-001"]


def test_implementation_is_selected_after_setup_completes() -> None:
    plan = {
        "tasks": [
            _task("TASK-001", "SETUP", status="COMPLETED"),
            _task("TASK-002", "IMPLEMENTATION", dependencies=["TASK-001"]),
        ],
        "execution_order": ["TASK-001", "TASK-002"],
    }

    selected = first_executable_task(plan)

    assert selected is not None
    assert selected["task_id"] == "TASK-002"


def test_task_with_incomplete_dependencies_is_not_selected() -> None:
    plan = {
        "tasks": [
            _task("TASK-001", "SETUP"),
            _task("TASK-002", "IMPLEMENTATION", dependencies=["TASK-001"]),
        ],
        "execution_order": ["TASK-002"],
    }

    selected = first_executable_task(plan)

    assert selected is not None
    assert selected["task_id"] == "TASK-001"
    assert dependency_status(plan, plan["tasks"][1]) == {
        "status": "BLOCKED",
        "dependencies": ["TASK-001"],
        "incomplete_dependencies": ["TASK-001"],
    }


def test_validation_becomes_executable_after_implementation_and_testing() -> None:
    plan = {
        "tasks": [
            _task("TASK-001", "IMPLEMENTATION", status="COMPLETED"),
            _task("TASK-002", "TESTING", dependencies=["TASK-001"], status="COMPLETED"),
            _task("TASK-003", "VALIDATION", dependencies=["TASK-001", "TASK-002"]),
        ],
        "execution_order": ["TASK-001", "TASK-002", "TASK-003"],
    }

    selected = first_executable_task(plan)

    assert selected is not None
    assert selected["task_id"] == "TASK-003"


def test_deterministic_execution_order_is_preserved() -> None:
    plan = {
        "tasks": [
            _task("TASK-001", "DOCUMENTATION"),
            _task("TASK-002", "MIGRATION"),
        ],
        "execution_order": ["TASK-002", "TASK-001"],
    }

    assert first_executable_task(plan)["task_id"] == "TASK-002"


@pytest.mark.parametrize("task_type", list(PlanTaskType))
def test_every_supported_task_type_can_be_selected_and_completed(
    task_type: PlanTaskType,
) -> None:
    plan = {
        "tasks": [_task("TASK-001", task_type.value)],
        "execution_order": ["TASK-001"],
    }

    assert first_executable_task(plan)["task_id"] == "TASK-001"
    completed, changed = mark_task_completed(plan, "TASK-001")
    assert changed is True
    assert all_required_tasks_completed(completed) is True


def test_unsupported_task_type_cannot_silently_execute() -> None:
    plan = {
        "tasks": [_task("TASK-001", "DEPENDENCY_SETUP")],
        "execution_order": ["TASK-001"],
    }

    assert first_executable_task(plan) is None
    assert all_required_tasks_completed(plan) is False


def test_executable_plan_excludes_completed_tasks_without_reordering() -> None:
    plan = {
        "tasks": [
            _task("TASK-001", "SETUP", status="COMPLETED"),
            _task("TASK-002", "IMPLEMENTATION"),
        ],
        "execution_order": ["TASK-001", "TASK-002"],
    }

    coding_plan = executable_plan(plan)

    assert [task["task_id"] for task in coding_plan["tasks"]] == ["TASK-002"]
    assert coding_plan["execution_order"] == ["TASK-002"]


def test_completion_guard_requires_every_executable_task() -> None:
    plan = {
        "tasks": [
            _design_task(),
            _task("TASK-001", "SETUP"),
            _task("TASK-002", "IMPLEMENTATION", dependencies=["TASK-001"]),
        ],
        "execution_order": ["TASK-000", "TASK-001", "TASK-002"],
    }
    plan, _ = satisfy_approved_design_tasks(plan)

    plan, changed = mark_task_completed(plan, "TASK-001")

    assert changed is True
    assert all_required_tasks_completed(plan) is False
    assert first_executable_task(plan)["task_id"] == "TASK-002"
    plan, changed = mark_task_completed(plan, "TASK-002")
    assert changed is True
    assert all_required_tasks_completed(plan) is True
