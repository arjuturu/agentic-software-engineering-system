from copy import deepcopy

from app.schemas.agents.planning import PlanTaskType

_COMPLETED_STATUSES = {"COMPLETED", "SATISFIED"}
_ARTIFACT_TERMS = ("architecture", "implementation plan", "design plan")
_COMPLETION_TERMS = ("approv", "generat", "creat", "produc", "provid", "document")


def _is_completed(task: dict) -> bool:
    return str(task.get("status", "PLANNED")).upper() in _COMPLETED_STATUSES


def _ordered_tasks(plan: dict) -> list[dict]:
    tasks = {task["task_id"]: task for task in plan.get("tasks", [])}
    ordered = [tasks[task_id] for task_id in plan.get("execution_order", []) if task_id in tasks]
    ordered_ids = {task["task_id"] for task in ordered}
    ordered.extend(task for task in tasks.values() if task["task_id"] not in ordered_ids)
    return ordered


def _is_approved_design_artifact_task(task: dict) -> bool:
    # Historical checkpoints may contain the pre-enum DESIGN fixture value. New model output
    # cannot produce it because PlanTask.task_type is strict.
    if str(task.get("task_type", "")).strip().upper() == "DESIGN":
        criteria = [
            *task.get("acceptance_criteria_covered", []),
            *task.get("exit_criteria", []),
        ]
        for criterion in criteria:
            normalized = str(criterion).casefold()
            if any(term in normalized for term in _ARTIFACT_TERMS) and any(
                term in normalized for term in _COMPLETION_TERMS
            ):
                return True
    return False


def plan_task_type(value: object) -> PlanTaskType | None:
    try:
        return PlanTaskType(str(value))
    except ValueError:
        return None


def satisfy_approved_design_tasks(plan: dict) -> tuple[dict, list[str]]:
    """Mark approved architecture/plan artifact tasks complete without removing them."""
    updated = deepcopy(plan)
    satisfied: list[str] = []
    for task in updated.get("tasks", []):
        if _is_approved_design_artifact_task(task):
            task["status"] = "COMPLETED"
            task["completion_source"] = "ARCHITECTURE_AND_PLAN_APPROVAL"
            satisfied.append(task["task_id"])
    return updated, satisfied


def dependency_status(plan: dict, task: dict) -> dict[str, object]:
    tasks = {item["task_id"]: item for item in plan.get("tasks", [])}
    dependencies = list(task.get("dependencies", []))
    incomplete = [
        dependency
        for dependency in dependencies
        if dependency not in tasks or not _is_completed(tasks[dependency])
    ]
    return {
        "status": "READY" if not incomplete else "BLOCKED",
        "dependencies": dependencies,
        "incomplete_dependencies": incomplete,
    }


def first_executable_task(plan: dict) -> dict | None:
    """Select the first dependency-ready executable task in approved plan order."""
    for task in _ordered_tasks(plan):
        task_type = plan_task_type(task.get("task_type"))
        if (
            not _is_completed(task)
            and task_type is not None
            and dependency_status(plan, task)["status"] == "READY"
        ):
            return deepcopy(task)
    return None


def mark_task_completed(plan: dict, task_id: str) -> tuple[dict, bool]:
    """Return a plan with one task completed, preserving plan order and metadata."""
    updated = deepcopy(plan)
    changed = False
    for task in updated.get("tasks", []):
        if task.get("task_id") == task_id and not _is_completed(task):
            task["status"] = "COMPLETED"
            changed = True
            break
    return updated, changed


def required_executable_tasks(plan: dict) -> list[dict]:
    """Return executable tasks in their approved deterministic execution order."""
    return [
        deepcopy(task)
        for task in _ordered_tasks(plan)
        if plan_task_type(task.get("task_type")) is not None
    ]


def unfinished_executable_task_ids(plan: dict) -> list[str]:
    return [
        task["task_id"] for task in required_executable_tasks(plan) if not _is_completed(task)
    ]


def all_required_tasks_completed(plan: dict) -> bool:
    tasks = required_executable_tasks(plan)
    return bool(tasks) and all(_is_completed(task) for task in tasks)


def unfinished_task_ids(plan: dict) -> list[str]:
    return [task["task_id"] for task in _ordered_tasks(plan) if not _is_completed(task)]


def executable_plan(plan: dict) -> dict:
    """Keep original task order while excluding already satisfied tasks from coding input."""
    result = deepcopy(plan)
    tasks = [task for task in result.get("tasks", []) if not _is_completed(task)]
    task_ids = {task["task_id"] for task in tasks}
    result["tasks"] = tasks
    result["execution_order"] = [
        task_id for task_id in result.get("execution_order", []) if task_id in task_ids
    ]
    return result
