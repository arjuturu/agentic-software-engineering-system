import pytest
from pydantic import ValidationError

from app.agents.planning_agent import PlanningAgent
from app.orchestration.planning_policy import (
    PlanValidator,
    normalize_scenario_path_policy,
)
from app.schemas.agents.planning import PlanTask


def _task(**updates: object) -> dict:
    task = {
        "task_id": "TASK-001",
        "title": "Implement application",
        "description": "Create the application entry point.",
        "task_type": "IMPLEMENTATION",
        "dependencies": [],
        "expected_files": ["app/main.py"],
        "allowed_paths": ["app"],
        "acceptance_criteria_covered": [],
    }
    task.update(updates)
    return task


def _plan(
    task: dict | None = None,
    *,
    tasks: list[dict] | None = None,
    status: str = "PLAN_COMPLETE",
) -> dict:
    tasks = tasks if tasks is not None else ([] if task is None else [task])
    return {
        "status": status,
        "tasks": tasks,
        "execution_order": [item["task_id"] for item in tasks],
    }


def _validate(plan: dict, profile: dict) -> tuple[dict[str, object], ...]:
    result = PlanValidator().validate(
        plan,
        normalize_scenario_path_policy(profile),
        approved_requirement={},
        architecture_design={"implementation_feasible": True, "components": []},
    )
    return result.errors


def test_empty_scenario_restrictions_are_task_scoped_and_executable() -> None:
    profile = {"allowed_paths": []}
    policy = normalize_scenario_path_policy(profile)

    errors = _validate(_plan(_task()), profile)

    assert policy == {
        "mode": "TASK_SCOPED",
        "scenario_restrictions": [],
        "meaning": (
            "No additional scenario-level restriction. Every task must declare explicit "
            "workspace-relative allowed paths."
        ),
    }
    assert errors == ()


def test_nonempty_scenario_restrictions_constrain_task_paths() -> None:
    profile = {"allowed_paths": ["app"]}
    assert _validate(_plan(_task()), profile) == ()

    errors = _validate(
        _plan(_task(expected_files=["tests/test_api.py"], allowed_paths=["tests"])),
        profile,
    )

    assert "SCENARIO_PATH_RESTRICTION" in {item["code"] for item in errors}


def test_explicit_deny_all_blocks_planning() -> None:
    profile = {"allowed_paths": [], "path_policy_mode": "DENY_ALL"}

    errors = _validate(_plan(_task()), profile)

    assert "SCENARIO_DENY_ALL" in {item["code"] for item in errors}


def test_code_changing_tasks_require_explicit_paths() -> None:
    errors = _validate(_plan(_task(allowed_paths=[])), {"allowed_paths": []})

    assert "TASK_PATHS_REQUIRED" in {item["code"] for item in errors}


def test_validation_only_task_may_have_no_paths() -> None:
    validation_task = _task(
        task_id="TASK-002",
        task_type="VALIDATION",
        title="Final validation",
        dependencies=["TASK-001"],
        expected_files=[],
        allowed_paths=[],
    )

    assert _validate(
        _plan(tasks=[_task(task_type="SETUP"), validation_task]), {"allowed_paths": []}
    ) == ()


def test_wildcard_paths_are_rejected() -> None:
    errors = _validate(_plan(_task(allowed_paths=["app/*"])), {"allowed_paths": []})

    assert "WILDCARD_PATH_BLOCKED" in {item["code"] for item in errors}


def test_every_expected_file_must_be_covered() -> None:
    errors = _validate(
        _plan(_task(expected_files=["app/main.py"], allowed_paths=["tests"])),
        {"allowed_paths": []},
    )

    assert "EXPECTED_FILE_NOT_ALLOWED" in {item["code"] for item in errors}


def test_blocked_plan_cannot_blame_empty_scenario_paths() -> None:
    result = PlanValidator().validate(
        _plan(status="BLOCKED"),
        normalize_scenario_path_policy({"allowed_paths": []}),
        approved_requirement={"status": "READY_FOR_APPROVAL"},
        architecture_design={"implementation_feasible": True},
    )

    assert "EMPTY_SCENARIO_PATHS_NOT_BLOCKING" in {
        item["code"] for item in result.errors
    }


def test_planning_agent_receives_normalized_policy_not_raw_allowlist() -> None:
    captured: dict = {}

    class FakeRunner:
        def run(self, **kwargs):
            captured.update(kwargs)
            return {"status": "PLAN_COMPLETE"}

    state = {
        "workflow_id": "WF-TEST",
        "scenario_type": "GREENFIELD",
        "scripted_scenario": "HAPPY_PATH",
        "scenario_profile": {
            "profile_id": "GENERIC",
            "scenario_type": "GREENFIELD",
            "summary": "Generic",
            "required_capabilities": [],
            "validation_rules": [],
            "allowed_paths": [],
            "path_policy_mode": "TASK_SCOPED",
        },
        "approved_requirement": {},
        "architecture_design": {},
    }

    PlanningAgent(FakeRunner()).run(state)

    payload = captured["input_payload"]
    assert "allowed_paths" not in payload["scenario_profile"]
    assert payload["scenario_path_policy"]["mode"] == "TASK_SCOPED"
    assert payload["scenario_path_policy"]["scenario_restrictions"] == []
    assert payload["pre_satisfied_capabilities"] == [
        "ARCHITECTURE_ARTIFACT_GENERATED",
        "IMPLEMENTATION_PLAN_ARTIFACT_GENERATED",
    ]
    assert payload["pending_orchestration_gate"] == "ARCHITECTURE_AND_PLAN"
    assert payload["post_approval_plan"] is True


def test_exact_task_id_mismatch_and_references_are_rejected() -> None:
    plan = _plan(_task())
    plan.update(
        execution_order=["T001"],
        critical_path=["T001"],
        parallel_groups=[["T001"]],
    )
    plan["tasks"][0]["dependencies"] = ["T000"]

    codes = {item["code"] for item in _validate(plan, {"allowed_paths": []})}

    assert codes >= {
        "EXECUTION_ORDER_INVALID",
        "CRITICAL_PATH_REFERENCE_INVALID",
        "PARALLEL_GROUP_REFERENCE_INVALID",
        "DEPENDENCY_REFERENCE_INVALID",
    }


def test_presatisfied_governance_tasks_are_rejected() -> None:
    architecture = _task(
        title="Generate architecture design artifact",
        description="Create architecture Markdown.",
        expected_files=["architecture-design.md"],
        allowed_paths=["architecture-design.md"],
    )
    approval = _task(
        task_id="TASK-002",
        title="Obtain architecture and plan approval",
        description="Execute the ARCHITECTURE_AND_PLAN approval gate.",
        dependencies=["TASK-001"],
        expected_files=[],
        allowed_paths=["approval.txt"],
    )
    application = _task(
        task_id="TASK-003",
        dependencies=["TASK-002"],
    )

    codes = {
        item["code"]
        for item in _validate(
            _plan(tasks=[architecture, approval, application]), {"allowed_paths": []}
        )
    }

    assert codes >= {
        "DUPLICATE_UPSTREAM_ARTIFACT_TASK",
        "ORCHESTRATION_GATE_AS_EXECUTABLE_TASK",
        "APPLICATION_DEPENDS_ON_DUPLICATE_GOVERNANCE_TASK",
    }


def test_wf_9c6c4f20bbbd_v3_governance_classification_passes() -> None:
    tasks = [
        _task(
            task_id="TASK-017",
            task_type="SETUP",
            title="Initialize project and governed tool configuration",
            expected_files=["pyproject.toml"],
            allowed_paths=["pyproject.toml"],
        ),
        _task(
            task_id="TASK-028",
            task_type="MIGRATION",
            title="Implement SQLite persistence and Alembic schema migration",
            dependencies=["TASK-017"],
            expected_files=["alembic/env.py"],
            allowed_paths=["alembic"],
        ),
        _task(
            task_id="TASK-039",
            task_type="IMPLEMENTATION",
            title="Implement validation, short-code allocation, and URL mapping service",
            dependencies=["TASK-028"],
            expected_files=["app/services.py"],
            allowed_paths=["app"],
        ),
        _task(
            task_id="TASK-040",
            task_type="INTEGRATION",
            title="Compose FastAPI routes, application wiring, and operational documentation",
            description=(
                "Produce repository operational and release documentation without recreating "
                "upstream architecture or implementation-plan artifacts."
            ),
            dependencies=["TASK-039"],
            expected_files=[
                "app/main.py",
                "README.md",
                "docs/validation.md",
                "docs/change-summary.md",
                "docs/pr-summary.md",
                "docs/known-limitations.md",
            ],
            allowed_paths=["app", "README.md", "docs"],
            entry_criteria=[
                "Approved architecture-design and implementation-plan artifacts are "
                "pre-satisfied and are not target-workspace deliverables."
            ],
            exit_criteria=[
                "No documentation recreates the upstream architecture-design or "
                "implementation-plan artifacts."
            ],
        ),
        _task(
            task_id="TASK-051",
            task_type="TESTING",
            title="Add isolated acceptance and lifecycle test coverage",
            dependencies=["TASK-040"],
            expected_files=["tests/test_application_contract.py"],
            allowed_paths=["tests"],
        ),
        _task(
            task_id="TASK-073",
            task_type="VALIDATION",
            title="Execute final deterministic quality gates",
            dependencies=["TASK-051"],
            expected_files=[],
            allowed_paths=[],
        ),
    ]

    assert _validate(_plan(tasks=tasks), {"allowed_paths": []}) == ()


def test_integration_may_reference_approved_upstream_artifacts() -> None:
    integration = _task(
        task_id="TASK-002",
        task_type="INTEGRATION",
        title="Wire approved application components",
        description=(
            "Consume the approved architecture and implementation plan for traceability; "
            "the approval remains outside the executable plan."
        ),
        dependencies=["TASK-001"],
        expected_files=["README.md", "docs/validation.md", "docs/change-summary.md"],
        allowed_paths=["README.md", "docs"],
    )

    assert _validate(
        _plan(tasks=[_task(task_type="SETUP"), integration]), {"allowed_paths": []}
    ) == ()


def test_explicit_current_approval_gate_action_is_rejected() -> None:
    approval = _task(
        task_id="TASK-002",
        title="Wait for ARCHITECTURE_AND_PLAN approval",
        description="Treat the human approval as executable work.",
        dependencies=["TASK-001"],
        expected_files=[],
        allowed_paths=["approval.txt"],
    )

    codes = {
        error["code"]
        for error in _validate(
            _plan(tasks=[_task(task_type="SETUP"), approval]), {"allowed_paths": []}
        )
    }

    assert "ORCHESTRATION_GATE_AS_EXECUTABLE_TASK" in codes


@pytest.mark.parametrize("artifact", ["architecture-design.md", "implementation-plan.md"])
def test_exact_upstream_artifact_regeneration_is_rejected(artifact: str) -> None:
    duplicate = _task(
        task_id="TASK-002",
        title=f"Regenerate {artifact}",
        dependencies=["TASK-001"],
        expected_files=[artifact],
        allowed_paths=[artifact],
    )

    codes = {
        error["code"]
        for error in _validate(
            _plan(tasks=[_task(task_type="SETUP"), duplicate]), {"allowed_paths": []}
        )
    }

    assert "DUPLICATE_UPSTREAM_ARTIFACT_TASK" in codes


def test_dependency_error_only_cascades_from_a_true_governance_task() -> None:
    valid_integration = _task(
        task_id="TASK-002",
        task_type="INTEGRATION",
        title="Document approved architecture integration",
        description="Do not regenerate the approved implementation plan.",
        dependencies=["TASK-001"],
        expected_files=["README.md"],
        allowed_paths=["README.md"],
    )
    dependent = _task(
        task_id="TASK-003",
        task_type="TESTING",
        dependencies=["TASK-002"],
        expected_files=["tests/test_api.py"],
        allowed_paths=["tests"],
    )
    valid_codes = {
        error["code"]
        for error in _validate(
            _plan(tasks=[_task(task_type="SETUP"), valid_integration, dependent]),
            {"allowed_paths": []},
        )
    }
    invalid_gate = {
        **valid_integration,
        "title": "Request ARCHITECTURE_AND_PLAN approval",
    }
    invalid_codes = {
        error["code"]
        for error in _validate(
            _plan(tasks=[_task(task_type="SETUP"), invalid_gate, dependent]),
            {"allowed_paths": []},
        )
    }

    assert "APPLICATION_DEPENDS_ON_DUPLICATE_GOVERNANCE_TASK" not in valid_codes
    assert "APPLICATION_DEPENDS_ON_DUPLICATE_GOVERNANCE_TASK" in invalid_codes


def test_post_approval_plan_requires_setup_or_implementation_first() -> None:
    testing = _task(task_type="TESTING", title="Run tests")
    codes = {item["code"] for item in _validate(_plan(testing), {"allowed_paths": []})}

    assert "NO_POST_APPROVAL_IMPLEMENTATION_TASK" in codes
    assert "POST_APPROVAL_TASK_ORDER_INVALID" in codes


def test_unsupported_model_task_type_fails_structured_output_parsing() -> None:
    with pytest.raises(ValidationError):
        PlanTask.model_validate(
            {
                "task_id": "TASK-001",
                "title": "Unsupported dependency setup",
                "description": "Invalid semantic synonym.",
                "task_type": "DEPENDENCY_SETUP",
                "dependencies": [],
                "parallel_group": None,
                "risk_level": "LOW",
                "expected_files": ["pyproject.toml"],
                "allowed_paths": ["pyproject.toml"],
                "entry_criteria": [],
                "exit_criteria": [],
                "validation_commands": ["RUFF_CHECK"],
                "acceptance_criteria_covered": [],
            }
        )


def test_required_execution_stages_are_enforced() -> None:
    result = PlanValidator().validate(
        _plan(_task()),
        normalize_scenario_path_policy({"allowed_paths": []}),
        approved_requirement={
            "functional_requirements": ["Provide a FastAPI service endpoint."],
            "acceptance_criteria": ["The endpoint passes acceptance tests."],
        },
        architecture_design={
            "implementation_feasible": True,
            "components": [{"name": "api"}, {"name": "service"}],
        },
    )

    codes = {item["code"] for item in result.errors}
    assert "DEPENDENCY_SETUP_REQUIRED" in codes
    assert "INTEGRATION_TASK_REQUIRED" in codes
    assert "ACCEPTANCE_TEST_TASK_REQUIRED" in codes
    assert "FINAL_VALIDATION_TASK_REQUIRED" in codes
