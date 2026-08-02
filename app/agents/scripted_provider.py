from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.schemas.agents.coding import (
    CodingOutput,
    RepositoryAnalysisOutput,
)
from app.schemas.agents.common import ScriptedScenario
from app.schemas.agents.design import DesignOutput
from app.schemas.agents.planning import PlanningOutput
from app.schemas.agents.release import ReleaseOutput
from app.schemas.agents.requirement import RequirementOutput
from app.schemas.agents.validation import ValidationOutput


class ScriptedProvider:
    """Return deterministic, separate structured outputs for offline workflow tests."""

    def generate(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        input_payload: dict,
        output_model: type[BaseModel],
    ) -> BaseModel:
        del system_prompt
        scenario = ScriptedScenario(
            input_payload.get("scripted_scenario", ScriptedScenario.HAPPY_PATH)
        )
        retry_number = int(input_payload.get("retry_number", 0))
        builders = {
            RequirementOutput: self._requirement,
            DesignOutput: self._design,
            PlanningOutput: self._planning,
            RepositoryAnalysisOutput: self._repository_analysis,
            CodingOutput: self._coding,
            ValidationOutput: self._validation,
            ReleaseOutput: self._release,
        }
        builder = builders.get(output_model)
        if builder is None:
            raise ValueError(f"Unsupported scripted output model for {agent_name}.")
        data = builder(input_payload, scenario, retry_number)
        return output_model.model_validate(data)

    @staticmethod
    def _requirement(
        payload: dict[str, Any], scenario: ScriptedScenario, retry_number: int
    ) -> dict[str, Any]:
        del retry_number
        requirement = payload.get("original_requirement", "Create a small Python service.")
        answers = payload.get("clarification_answers", [])
        if scenario == ScriptedScenario.REQUIREMENT_REJECTED:
            status = "REJECTED_AS_UNSAFE"
            questions: list[dict[str, str]] = []
            ambiguity = False
        elif scenario == ScriptedScenario.CLARIFICATION_REQUIRED and not answers:
            status = "CLARIFICATION_REQUIRED"
            questions = [
                {
                    "question_id": "Q-001",
                    "question": "Should the sample expose a deterministic greeting function?",
                }
            ]
            ambiguity = True
        else:
            status = "READY_FOR_APPROVAL"
            questions = []
            ambiguity = False
        return {
            "normalized_requirement": requirement.strip(),
            "functional_requirements": [
                "Provide a deterministic Python function.",
                "Include automated tests.",
            ],
            "non_functional_requirements": [
                "Use Python 3.11 or newer.",
                "Remain offline and deterministic.",
            ],
            "assumptions": ["The target is a minimal greenfield Python package."],
            "ambiguities": ["Greeting behavior requires confirmation."] if ambiguity else [],
            "clarification_questions": questions,
            "acceptance_criteria": [
                "Ruff completes successfully.",
                "Pytest completes successfully.",
            ],
            "risks": ["Generated content must remain inside the target workspace."],
            "material_ambiguity": ambiguity,
            "risk_level": "LOW",
            "status": status,
        }

    @staticmethod
    def _design(
        payload: dict[str, Any], scenario: ScriptedScenario, retry_number: int
    ) -> dict[str, Any]:
        del payload, scenario
        return {
            "architecture_summary": (
                "A small dependency-free Python package with isolated tests "
                f"(design iteration {retry_number + 1})."
            ),
            "components": [
                {
                    "name": "sample_app",
                    "responsibility": "Deterministic application logic",
                    "interfaces": ["greeting()"],
                    "dependencies": [],
                },
                {
                    "name": "tests",
                    "responsibility": "Behavioral verification",
                    "interfaces": ["pytest"],
                    "dependencies": ["sample_app"],
                },
            ],
            "api_design": [
                {
                    "name": "greeting",
                    "method_or_type": "Python function",
                    "path_or_signature": "greeting() -> str",
                    "purpose": "Return the deterministic greeting",
                }
            ],
            "data_design": [],
            "control_flow": ["Caller invokes greeting", "Function returns a constant string"],
            "security_controls": ["No network, secrets, dynamic execution, or external paths"],
            "reliability_controls": ["Deterministic output", "Automated tests"],
            "observability_controls": ["Validation command results are captured as artifacts"],
            "architecture_decisions": [
                {
                    "decision": "Use a package function",
                    "rationale": "Keep the scripted fixture minimal",
                    "alternatives": ["HTTP service"],
                    "consequences": ["HTTP behavior is deferred"],
                }
            ],
            "risks": [],
            "trade_offs": ["Minimal scope favors demonstrability over feature breadth"],
            "limitations": ["This is a generic workflow fixture, not a URL shortener"],
            "implementation_feasible": True,
            "status": "DESIGN_COMPLETE",
        }

    @staticmethod
    def _planning(
        payload: dict[str, Any], scenario: ScriptedScenario, retry_number: int
    ) -> dict[str, Any]:
        del retry_number
        package_name = (
            "app"
            if payload.get("scenario_profile", {}).get("profile_id")
            == "URL_SHORTENER_GREENFIELD"
            else "sample_app"
        )
        tasks = [
            {
                "task_id": "TASK-001",
                "title": "Set up project dependencies",
                "description": "Create deterministic package metadata and tool configuration.",
                "task_type": "SETUP",
                "dependencies": [],
                "parallel_group": None,
                "risk_level": "LOW",
                "expected_files": ["pyproject.toml"],
                "allowed_paths": ["pyproject.toml"],
                "entry_criteria": ["Architecture approved"],
                "exit_criteria": ["Project metadata is valid"],
                "validation_commands": ["RUFF_CHECK"],
                "acceptance_criteria_covered": ["Ruff completes successfully."],
            },
            {
                "task_id": "TASK-002",
                "title": "Implement runnable application entry point",
                "description": "Create the deterministic package and its main application logic.",
                "task_type": "IMPLEMENTATION",
                "dependencies": ["TASK-001"],
                "parallel_group": None,
                "risk_level": "LOW",
                "expected_files": [f"{package_name}/__init__.py", f"{package_name}/main.py"],
                "allowed_paths": (
                    [package_name, "tests"]
                    if scenario == ScriptedScenario.CODING_RETRY_THEN_PASS
                    else [package_name]
                ),
                "entry_criteria": ["Dependency setup completed"],
                "exit_criteria": ["Application entry point imports"],
                "validation_commands": (
                    ["RUFF_CHECK", "PYTEST"]
                    if scenario == ScriptedScenario.CODING_RETRY_THEN_PASS
                    else ["RUFF_CHECK"]
                ),
                "acceptance_criteria_covered": ["Application behavior is implemented."],
            },
            {
                "task_id": "TASK-003",
                "title": "Wire application integration",
                "description": "Connect the package entry point to the implemented behavior.",
                "task_type": "IMPLEMENTATION",
                "dependencies": ["TASK-002"],
                "parallel_group": None,
                "risk_level": "LOW",
                "expected_files": [],
                "allowed_paths": [package_name],
                "entry_criteria": ["Application implementation completed"],
                "exit_criteria": ["Application wiring is complete"],
                "validation_commands": ["RUFF_CHECK"],
                "acceptance_criteria_covered": ["Application components are integrated."],
            },
            {
                "task_id": "TASK-004",
                "title": "Create acceptance tests",
                "description": "Verify the deterministic application behavior.",
                "task_type": "TESTING",
                "dependencies": ["TASK-003"],
                "parallel_group": None,
                "risk_level": "LOW",
                "expected_files": ["tests/test_main.py"],
                "allowed_paths": ["tests"],
                "entry_criteria": ["Application wiring completed"],
                "exit_criteria": ["Acceptance tests pass"],
                "validation_commands": ["PYTEST"],
                "acceptance_criteria_covered": ["Pytest completes successfully."],
            },
            {
                "task_id": "TASK-005",
                "title": "Run final validation",
                "description": "Run the complete approved quality suite.",
                "task_type": "VALIDATION",
                "dependencies": ["TASK-004"],
                "parallel_group": None,
                "risk_level": "LOW",
                "expected_files": [],
                "allowed_paths": [],
                "entry_criteria": ["Acceptance tests completed"],
                "exit_criteria": ["Final validation passes"],
                "validation_commands": ["RUFF_CHECK", "PYTEST"],
                "acceptance_criteria_covered": [
                    "Ruff completes successfully.",
                    "Pytest completes successfully.",
                ],
            },
        ]
        return {
            "plan_summary": "Create the package, then verify it with Ruff and Pytest.",
            "tasks": tasks,
            "execution_order": ["TASK-001", "TASK-002", "TASK-003", "TASK-004", "TASK-005"],
            "parallel_groups": [],
            "critical_path": ["TASK-001", "TASK-002", "TASK-003", "TASK-004", "TASK-005"],
            "high_risk_tasks": [],
            "assumptions": ["Required validation tools are installed by the control plane."],
            "implementation_risks": [],
            "status": "PLAN_COMPLETE",
        }

    @staticmethod
    def _repository_analysis(
        payload: dict[str, Any], scenario: ScriptedScenario, retry_number: int
    ) -> dict[str, Any]:
        del scenario, retry_number
        scan = payload.get("deterministic_scan", {})
        project_files = scan.get("detected_project_files", [])
        package_name = (
            "app"
            if payload.get("scenario_profile", {}).get("profile_id")
            == "URL_SHORTENER_GREENFIELD"
            else "sample_app"
        )
        return {
            "repository_summary": scan.get("repository_summary", "Empty greenfield repository"),
            "detected_frameworks": ["Python"] if project_files else [],
            "project_structure": project_files,
            "impacted_modules": [package_name],
            "impacted_files": [
                "pyproject.toml",
                f"{package_name}/__init__.py",
                f"{package_name}/main.py",
                "tests/test_main.py",
            ],
            "existing_tests": scan.get("detected_test_files", []),
            "existing_migrations": scan.get("detected_migration_files", []),
            "coding_conventions": ["Python 3.11", "Ruff"],
            "compatibility_risks": [],
            "recommended_allowed_paths": ["pyproject.toml", package_name, "tests"],
            "blocked_or_sensitive_paths": scan.get("restricted_files_found", []),
            "architecture_compatible": not scan.get("restricted_files_found"),
            "status": (
                "ANALYSIS_COMPLETE" if not scan.get("restricted_files_found") else "BLOCKED"
            ),
        }
    @staticmethod
    def _create_edits(
        main_result: str, package_name: str = "sample_app"
    ) -> list[dict[str, Any]]:
        return [
            {
                "operation": "CREATE",
                "relative_path": "pyproject.toml",
                "content": (
                    '[project]\nname = "governed-sample"\nversion = "0.1.0"\n'
                    'requires-python = ">=3.11"\n\n[tool.ruff]\nline-length = 100\n'
                    'target-version = "py311"\n'
                ),
            },
            {
                "operation": "CREATE",
                "relative_path": f"{package_name}/__init__.py",
                "content": (
                    f"from {package_name}.main import greeting\n\n"
                    '__all__ = ["greeting"]\n'
                ),
            },
            {
                "operation": "CREATE",
                "relative_path": f"{package_name}/main.py",
                "content": f'def greeting() -> str:\n    return "{main_result}"\n',
            },
            {
                "operation": "CREATE",
                "relative_path": "tests/test_main.py",
                "content": (
                    f"from {package_name}.main import greeting\n\n\n"
                    'def test_greeting() -> None:\n    assert greeting() == "hello"\n'
                ),
            },
        ]

    def _coding(
        self,
        payload: dict[str, Any],
        scenario: ScriptedScenario,
        retry_number: int,
    ) -> dict[str, Any]:
        package_name = (
            "app"
            if payload.get("scenario_profile", {}).get("profile_id")
            == "URL_SHORTENER_GREENFIELD"
            else "sample_app"
        )
        if scenario == ScriptedScenario.POLICY_VIOLATION:
            edits = [
                {
                    "operation": "CREATE",
                    "relative_path": ".env",
                    "content": "OPENAI_API_KEY=forbidden",
                }
            ]
            status = "READY_TO_APPLY"
        elif (
            scenario == ScriptedScenario.CODING_RETRY_THEN_PASS
            and retry_number > 0
            and payload.get("originating_task") is not None
        ):
            edits = [
                {
                    "operation": "MODIFY",
                    "relative_path": f"{package_name}/main.py",
                    "expected_hash": payload.get("file_hashes", {}).get(
                        f"{package_name}/main.py", ""
                    ),
                    "old_text": 'return "wrong"',
                    "replacement_text": 'return "hello"',
                }
            ]
            status = "READY_TO_APPLY"
        else:
            result = (
                "wrong"
                if scenario == ScriptedScenario.CODING_RETRY_THEN_PASS and retry_number == 0
                else "hello"
            )
            edits = self._create_edits(result, package_name)
            active_task = payload.get("active_task", {})
            expected_files = set(active_task.get("expected_files", []))
            allowed_paths = [str(path).rstrip("/") for path in active_task.get("allowed_paths", [])]
            if not expected_files and not allowed_paths:
                edits = []
            else:
                expected_directories = {
                    str(Path(path).parent).replace("\\", "/")
                    for path in expected_files
                    if "/" in str(path).replace("\\", "/")
                }
                edits = [
                    edit
                    for edit in edits
                    if edit["relative_path"] in expected_files
                    or any(
                        edit["relative_path"].startswith(f"{path}/")
                        for path in expected_directories
                    )
                    or any(
                        edit["relative_path"].startswith(f"{path}/")
                        for path in allowed_paths
                    )
                ]
            existing_hashes = payload.get("file_hashes", {})
            edits = [
                edit
                for edit in edits
                if edit["operation"] != "CREATE"
                or edit["relative_path"] not in existing_hashes
            ]
            status = "READY_TO_APPLY"
        for edit in edits:
            is_create = edit["operation"] == "CREATE"
            edit.setdefault("content", None)
            edit.setdefault("expected_absent", is_create)
            edit.setdefault("expected_hash", None)
            edit.setdefault("old_text", None)
            edit.setdefault("replacement_text", None)
        active_task_id = payload.get("active_task", {}).get("task_id", "TASK-001")
        return {
            "implementation_summary": "Create or correct the deterministic sample package.",
            "change_plan": [
                {"task_id": active_task_id, "paths": [edit["relative_path"] for edit in edits]}
            ],
            "structured_edits": edits,
            "tests_created_or_modified": ["tests/test_main.py"],
            "migrations_created": [],
            "assumptions": ["No dependency installation is required."],
            "risks": [],
            "dependency_changes": [],
            "high_risk_change": False,
            "high_risk_reason": None,
            "status": status,
            "replan_reason": None,
        }

    @staticmethod
    def _validation(
        payload: dict[str, Any], scenario: ScriptedScenario, retry_number: int
    ) -> dict[str, Any]:
        results = payload.get("command_results", [])
        commands_passed = bool(results) and all(
            result.get("status") == "SUCCESS" for result in results
        )
        if scenario in {
            ScriptedScenario.VALIDATION_FAILURE,
            ScriptedScenario.ROLLBACK_REQUIRED,
        }:
            passed = False
            category = "UNKNOWN_FAILURE"
            rollback = True
            retry = False
        elif scenario == ScriptedScenario.CODING_RETRY_THEN_PASS and retry_number == 0:
            passed = False
            category = "IMPLEMENTATION_DEFECT"
            rollback = False
            retry = True
        else:
            passed = commands_passed
            category = None if passed else "IMPLEMENTATION_DEFECT"
            rollback = False
            retry = not passed
        criteria = payload.get("approved_requirement", {}).get(
            "acceptance_criteria", ["Quality commands pass"]
        )
        return {
            "acceptance_criteria_results": [
                {
                    "criterion": criterion,
                    "status": "PASSED" if passed else "FAILED",
                    "evidence": ["Ruff and pytest command results"],
                }
                for criterion in criteria
            ],
            "tests_executed": 1,
            "tests_passed": 1 if passed else 0,
            "tests_failed": 0 if passed else 1,
            "tests_skipped": 0,
            "lint_status": "PASSED" if passed else "FAILED",
            "migration_status": "NOT_APPLICABLE",
            "architecture_compliance": passed,
            "findings": [] if passed else ["The generated implementation did not validate."],
            "failure_category": category,
            "retry_recommended": retry,
            "replan_recommended": False,
            "rollback_recommended": rollback,
            "release_recommendation": "READY" if passed else "NOT_READY",
            "status": "VALIDATION_PASSED" if passed else "VALIDATION_FAILED",
        }

    @staticmethod
    def _release(
        payload: dict[str, Any], scenario: ScriptedScenario, retry_number: int
    ) -> dict[str, Any]:
        del scenario, retry_number
        validation = payload.get("validation_result", {})
        passed = validation.get("status") == "VALIDATION_PASSED"
        return {
            "change_summary": "Created a governed generic Python sample.",
            "requirement_completion_summary": "Approved acceptance criteria were evaluated.",
            "architecture_summary": "A small package and isolated tests were created.",
            "implementation_summary": "Structured edits were applied and committed locally.",
            "testing_summary": "Actual validation evidence was consumed.",
            "security_summary": "Path, command, and local Git policies remained active.",
            "changed_files": payload.get("context", {}).get("changed_files", []),
            "generated_artifacts": payload.get("context", {}).get("artifacts", []),
            "known_risks": [],
            "known_limitations": ["The fixture is intentionally generic."],
            "conditions_for_release": [],
            "rollback_instructions": ["Restore tracked files to the recorded baseline commit."],
            "recommended_status": "READY" if passed else "NOT_READY",
            "recommendation_reason": (
                "Validation passed." if passed else "Validation evidence did not pass."
            ),
        }
