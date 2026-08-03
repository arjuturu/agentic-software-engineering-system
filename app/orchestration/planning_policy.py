import json
import re
from dataclasses import dataclass
from enum import StrEnum

from app.schemas.agents.planning import PlanTaskType
from app.tools.path_policy import PathPolicy, PathPolicyError


class ScenarioPathPolicyMode(StrEnum):
    TASK_SCOPED = "TASK_SCOPED"
    SCENARIO_RESTRICTED = "SCENARIO_RESTRICTED"
    DENY_ALL = "DENY_ALL"


_WILDCARD_CHARACTERS = frozenset("*?[")
_PRE_SATISFIED_CAPABILITIES = [
    "ARCHITECTURE_ARTIFACT_GENERATED",
    "IMPLEMENTATION_PLAN_ARTIFACT_GENERATED",
]
_NON_CORRECTABLE_ERRORS = {"SCENARIO_DENY_ALL"}
_UPSTREAM_ARTIFACT_NAMES = frozenset(
    {
        "architecture-design.md",
        "architecture-design.json",
        "architecture_plan.md",
        "architecture_plan.json",
        "implementation-plan.md",
        "implementation-plan.json",
        "requirement-analysis.md",
        "requirement-analysis.json",
    }
)
_CURRENT_GATE = "ARCHITECTURE_AND_PLAN"
_GATE_ACTION_PATTERN = re.compile(
    r"\b(?:request|obtain|await|wait\s+for|execute|perform)\s+(?:the\s+)?"
    r"(?:ARCHITECTURE_AND_PLAN|architecture(?:-design)?\s+(?:and|/)\s+"
    r"(?:implementation[- ]plan|plan))\s+(?:human\s+)?approval\b",
    re.IGNORECASE,
)
_GATE_DECISION_PATTERN = re.compile(
    r"\b(?:approve|reject)\s+(?:the\s+)?"
    r"(?:ARCHITECTURE_AND_PLAN|architecture(?:-design)?\s+(?:and|/)\s+"
    r"(?:implementation[- ]plan|plan))(?:\s+artifacts?)?\b",
    re.IGNORECASE,
)
_GATE_OUTPUT_PATTERN = re.compile(
    r"\b(?:ARCHITECTURE_AND_PLAN|architecture(?:-design)?\s+(?:and|/)\s+"
    r"(?:implementation[- ]plan|plan))\s+approval\s+(?:completion|decision)\s+"
    r"(?:is|as)\s+(?:the\s+)?task\s+output\b",
    re.IGNORECASE,
)


def normalize_scenario_path_policy(profile: dict) -> dict[str, object]:
    """Make the scenario path semantics explicit for planning and validation."""
    restrictions = PathPolicy.normalize_policy_paths(list(profile.get("allowed_paths", [])))
    configured_mode = str(profile.get("path_policy_mode", "")).strip().upper()
    if configured_mode == ScenarioPathPolicyMode.DENY_ALL:
        mode = ScenarioPathPolicyMode.DENY_ALL
        meaning = "No task may create or modify repository files."
    elif restrictions:
        mode = ScenarioPathPolicyMode.SCENARIO_RESTRICTED
        meaning = "Every task path must remain within the listed scenario restrictions."
    else:
        mode = ScenarioPathPolicyMode.TASK_SCOPED
        meaning = (
            "No additional scenario-level restriction. Every task must declare explicit "
            "workspace-relative allowed paths."
        )
    return {
        "mode": mode.value,
        "scenario_restrictions": restrictions,
        "meaning": meaning,
    }


def planning_scenario_context(profile: dict) -> dict[str, object]:
    """Return model-facing scenario metadata without ambiguous raw path fields."""
    return {
        "profile_id": profile.get("profile_id", "GENERIC"),
        "scenario_type": profile.get("scenario_type", ""),
        "summary": profile.get("summary", ""),
        "required_capabilities": list(profile.get("required_capabilities", [])),
        "validation_rules": list(profile.get("validation_rules", [])),
    }


def planning_governance_context() -> dict[str, object]:
    """Describe orchestration work that must not become executable plan tasks."""
    return {
        "pre_satisfied_capabilities": list(_PRE_SATISFIED_CAPABILITIES),
        "pending_orchestration_gate": "ARCHITECTURE_AND_PLAN",
        "post_approval_plan": True,
    }


@dataclass(frozen=True)
class PlanValidationResult:
    valid: bool
    errors: tuple[dict[str, object], ...] = ()

    @property
    def fixable(self) -> bool:
        return bool(self.errors) and not any(
            error.get("code") in _NON_CORRECTABLE_ERRORS for error in self.errors
        )


class PlanValidator:
    """Deterministically validate task paths and required plan structure."""

    def validate(
        self,
        plan: dict,
        scenario_path_policy: dict,
        *,
        approved_requirement: dict,
        architecture_design: dict,
    ) -> PlanValidationResult:
        errors: list[dict[str, object]] = []
        mode = str(scenario_path_policy.get("mode", ""))
        restrictions = list(scenario_path_policy.get("scenario_restrictions", []))
        tasks = list(plan.get("tasks", []))

        if mode == ScenarioPathPolicyMode.DENY_ALL:
            errors.append(self._error("SCENARIO_DENY_ALL", "Scenario policy denies file changes."))
        if plan.get("status") != "PLAN_COMPLETE" or not tasks:
            errors.append(self._error("PLAN_STATUS_INVALID", "The plan is not executable."))
            if (
                plan.get("status") == "BLOCKED"
                and mode == ScenarioPathPolicyMode.TASK_SCOPED
                and approved_requirement
                and architecture_design.get("implementation_feasible") is True
            ):
                errors.append(
                    self._error(
                        "EMPTY_SCENARIO_PATHS_NOT_BLOCKING",
                        "Empty scenario restrictions cannot block a task-scoped plan.",
                    )
                )

        task_id_list = [str(task.get("task_id", "")) for task in tasks]
        task_ids = set(task_id_list)
        if len(task_id_list) != len(task_ids):
            errors.append(self._error("TASK_IDS_INVALID", "Task IDs must be unique."))
        execution_order = list(plan.get("execution_order", []))
        invalid_execution_order = len(execution_order) != len(set(execution_order)) or set(
            execution_order
        ) != task_ids
        if tasks and invalid_execution_order:
            errors.append(
                self._error(
                    "EXECUTION_ORDER_INVALID",
                    "Execution order must contain every task exactly once.",
                )
            )

        self._validate_task_references(plan, tasks, task_ids, errors)

        for task in tasks:
            self._validate_task(task, mode, restrictions, errors)

        self._validate_required_capabilities(
            tasks, approved_requirement, architecture_design, errors
        )
        self._validate_governance_lifecycle(tasks, execution_order, errors)
        return PlanValidationResult(not errors, tuple(errors))

    def _validate_task_references(
        self,
        plan: dict,
        tasks: list[dict],
        task_ids: set[str],
        errors: list[dict[str, object]],
    ) -> None:
        for field, code in (
            ("critical_path", "CRITICAL_PATH_REFERENCE_INVALID"),
            ("high_risk_tasks", "HIGH_RISK_TASK_REFERENCE_INVALID"),
        ):
            unknown = sorted(set(map(str, plan.get(field, []))) - task_ids)
            if unknown:
                errors.append(self._reference_error(code, field, unknown))
        parallel_references = {
            str(task_id)
            for group in plan.get("parallel_groups", [])
            for task_id in group
        }
        unknown_parallel = sorted(parallel_references - task_ids)
        if unknown_parallel:
            errors.append(
                self._reference_error(
                    "PARALLEL_GROUP_REFERENCE_INVALID", "parallel_groups", unknown_parallel
                )
            )
        for task in tasks:
            unknown_dependencies = sorted(
                set(map(str, task.get("dependencies", []))) - task_ids
            )
            if unknown_dependencies:
                errors.append(
                    self._task_error(
                        str(task.get("task_id", "")),
                        "DEPENDENCY_REFERENCE_INVALID",
                        "Dependencies must reference exact existing task IDs.",
                        references=unknown_dependencies,
                    )
                )

    def _validate_task(
        self,
        task: dict,
        mode: str,
        restrictions: list[str],
        errors: list[dict[str, object]],
    ) -> None:
        task_id = str(task.get("task_id", ""))
        try:
            task_type = PlanTaskType(str(task.get("task_type", "")))
        except ValueError:
            errors.append(
                self._task_error(
                    task_id,
                    "TASK_TYPE_UNSUPPORTED",
                    "Task type must be one of the supported PlanTaskType values.",
                )
            )
            return
        expected_files = list(task.get("expected_files", []))
        allowed_paths = list(task.get("allowed_paths", []))
        validation_only = task_type == PlanTaskType.VALIDATION and not expected_files
        if not allowed_paths and not validation_only:
            errors.append(
                self._task_error(
                    task_id,
                    "TASK_PATHS_REQUIRED",
                    "Code-changing tasks require explicit allowed paths.",
                )
            )
            return

        normalized_allowed: list[str] = []
        for raw_path in allowed_paths:
            if any(character in str(raw_path) for character in _WILDCARD_CHARACTERS):
                errors.append(
                    self._task_error(
                        task_id, "WILDCARD_PATH_BLOCKED", "Wildcard task paths are not allowed."
                    )
                )
                continue
            try:
                normalized = PathPolicy.normalize_policy_path(str(raw_path))
            except PathPolicyError as exc:
                errors.append(self._task_error(task_id, exc.error_code, "Task path is unsafe."))
                continue
            if normalized != str(raw_path).replace("\\", "/"):
                errors.append(
                    self._task_error(
                        task_id,
                        "NON_CANONICAL_TASK_PATH",
                        "Task paths must use canonical workspace-relative notation.",
                    )
                )
            normalized_allowed.append(normalized)
            if restrictions and not any(
                PathPolicy._matches_allowed_path(normalized, restriction)
                for restriction in restrictions
            ):
                errors.append(
                    self._task_error(
                        task_id,
                        "SCENARIO_PATH_RESTRICTION",
                        "A task path is outside the scenario restriction.",
                    )
                )

        for expected_file in expected_files:
            try:
                normalized_file = PathPolicy.normalize_relative_path(str(expected_file))
            except PathPolicyError as exc:
                errors.append(
                    self._task_error(task_id, exc.error_code, "Expected file path is unsafe.")
                )
                continue
            if normalized_file != str(expected_file).replace("\\", "/"):
                errors.append(
                    self._task_error(
                        task_id,
                        "NON_CANONICAL_EXPECTED_FILE",
                        "Expected files must use canonical workspace-relative notation.",
                    )
                )
            if not any(
                PathPolicy._matches_allowed_path(normalized_file, allowed)
                for allowed in normalized_allowed
            ):
                errors.append(
                    self._task_error(
                        task_id,
                        "EXPECTED_FILE_NOT_ALLOWED",
                        "Every expected file must be covered by its task allowlist.",
                    )
                )

        if mode == ScenarioPathPolicyMode.DENY_ALL and (expected_files or allowed_paths):
            errors.append(
                self._task_error(task_id, "SCENARIO_DENY_ALL", "Scenario policy denies changes.")
            )

    def _validate_required_capabilities(
        self,
        tasks: list[dict],
        approved_requirement: dict,
        architecture_design: dict,
        errors: list[dict[str, object]],
    ) -> None:
        requirement_text = json.dumps(approved_requirement, sort_keys=True).casefold()
        architecture_text = json.dumps(architecture_design, sort_keys=True).casefold()
        task_texts = [
            " ".join(
                [
                    str(task.get("task_type", "")),
                    str(task.get("title", "")),
                    str(task.get("description", "")),
                    *map(str, task.get("acceptance_criteria_covered", [])),
                ]
            ).casefold()
            for task in tasks
        ]

        required: dict[str, tuple[bool, tuple[str, ...]]] = {
            "RUNNABLE_ENTRY_POINT_REQUIRED": (
                any(
                    term in requirement_text
                    for term in (" api", "endpoint", "service", "application")
                ),
                ("entry point", "main", "endpoint", "application"),
            ),
            "INTEGRATION_TASK_REQUIRED": (
                len(architecture_design.get("components", [])) > 1,
                ("integration", "wiring", "wire", "connect"),
            ),
            "DEPENDENCY_SETUP_REQUIRED": (
                any(
                    term in f"{requirement_text} {architecture_text}"
                    for term in ("dependency", "fastapi", "sqlalchemy", "framework", "package")
                ),
                ("setup", "dependency", "scaffold", "environment"),
            ),
            "ACCEPTANCE_TEST_TASK_REQUIRED": (
                bool(approved_requirement.get("acceptance_criteria"))
                or "test" in requirement_text,
                ("acceptance test", "testing", "test"),
            ),
            "FINAL_VALIDATION_TASK_REQUIRED": (
                bool(approved_requirement.get("acceptance_criteria")),
                ("final validation", "validation"),
            ),
        }
        for code, (is_required, terms) in required.items():
            if is_required and not any(any(term in text for term in terms) for text in task_texts):
                errors.append(self._error(code, "The plan omits a required execution stage."))

    def _validate_governance_lifecycle(
        self,
        tasks: list[dict],
        execution_order: list[str],
        errors: list[dict[str, object]],
    ) -> None:
        duplicated_governance: set[str] = set()
        executable_application: list[str] = []
        tasks_by_id = {str(task.get("task_id", "")): task for task in tasks}
        for task in tasks:
            task_id = str(task.get("task_id", ""))
            try:
                task_type = PlanTaskType(str(task.get("task_type", "")))
            except ValueError:
                task_type = None
            regenerates_upstream = self._regenerates_upstream_artifact(task)
            executes_gate = self._executes_current_approval_gate(task)
            if regenerates_upstream:
                duplicated_governance.add(task_id)
                errors.append(
                    self._task_error(
                        task_id,
                        "DUPLICATE_UPSTREAM_ARTIFACT_TASK",
                        "The plan must not regenerate approved architecture or planning artifacts.",
                    )
                )
            if executes_gate:
                duplicated_governance.add(task_id)
                errors.append(
                    self._task_error(
                        task_id,
                        "ORCHESTRATION_GATE_AS_EXECUTABLE_TASK",
                        "The current approval gate is an orchestration prerequisite, not a task.",
                    )
                )
            if task_type in {PlanTaskType.SETUP, PlanTaskType.IMPLEMENTATION} and not (
                regenerates_upstream or executes_gate
            ):
                executable_application.append(task_id)

        for task in tasks:
            if set(map(str, task.get("dependencies", []))) & duplicated_governance:
                errors.append(
                    self._task_error(
                        str(task.get("task_id", "")),
                        "APPLICATION_DEPENDS_ON_DUPLICATE_GOVERNANCE_TASK",
                        "Application tasks cannot depend on duplicated governance work.",
                    )
                )

        if tasks and not executable_application:
            errors.append(
                self._error(
                    "NO_POST_APPROVAL_IMPLEMENTATION_TASK",
                    "A post-approval plan requires an application setup or implementation task.",
                )
            )
        ordered_application = [
            task_id
            for task_id in execution_order
            if self._supported_task_type(
                tasks_by_id.get(str(task_id), {}).get("task_type", "")
            )
            and task_id not in duplicated_governance
        ]
        if ordered_application:
            first_type = self._supported_task_type(
                tasks_by_id.get(str(ordered_application[0]), {}).get("task_type", "")
            )
            if first_type not in {PlanTaskType.SETUP, PlanTaskType.IMPLEMENTATION}:
                errors.append(
                    self._error(
                        "POST_APPROVAL_TASK_ORDER_INVALID",
                        "Post-approval execution must begin with setup or implementation.",
                    )
                )

    @staticmethod
    def _supported_task_type(value: object) -> PlanTaskType | None:
        try:
            return PlanTaskType(str(value))
        except ValueError:
            return None

    def _regenerates_upstream_artifact(self, task: dict) -> bool:
        """Identify upstream outputs by declared artifact purpose or exact output filename."""
        purpose = str(task.get("artifact_purpose", "")).strip().upper()
        if purpose in {
            "UPSTREAM_REQUIREMENT_ANALYSIS",
            "UPSTREAM_ARCHITECTURE_DESIGN",
            "UPSTREAM_IMPLEMENTATION_PLAN",
        }:
            return True
        return any(
            self._is_upstream_artifact_path(str(path))
            for path in task.get("expected_files", [])
        )

    @staticmethod
    def _is_upstream_artifact_path(path: str) -> bool:
        normalized = path.replace("\\", "/").rsplit("/", 1)[-1].casefold()
        versionless = re.sub(r"^\d{2}-", "", normalized)
        versionless = re.sub(r"-v\d+(?=\.[^.]+$)", "", versionless)
        return versionless in _UPSTREAM_ARTIFACT_NAMES

    @staticmethod
    def _executes_current_approval_gate(task: dict) -> bool:
        """Recognize an explicit current-gate action, not incidental governance prose."""
        gate = str(
            task.get("orchestration_gate") or task.get("current_gate") or ""
        ).strip().upper()
        action = str(
            task.get("orchestration_gate_action") or task.get("gate_action") or ""
        ).strip().upper()
        if gate == _CURRENT_GATE and action in {
            "REQUEST",
            "WAIT",
            "APPROVE",
            "REJECT",
            "EXECUTE",
        }:
            return True

        # Schemas currently have no gate-action field, so narrowly recognize explicit
        # action statements in task identity fields. Criteria and assumptions are not scanned.
        identity_text = " ".join(
            (str(task.get("title", "")), str(task.get("description", "")))
        )
        return any(
            pattern.search(identity_text)
            for pattern in (
                _GATE_ACTION_PATTERN,
                _GATE_DECISION_PATTERN,
                _GATE_OUTPUT_PATTERN,
            )
        )

    @staticmethod
    def _error(code: str, message: str) -> dict[str, object]:
        return {"code": code, "message": message}

    @staticmethod
    def _task_error(
        task_id: str, code: str, message: str, **details: object
    ) -> dict[str, object]:
        return {"task_id": task_id, "code": code, "message": message, **details}

    @staticmethod
    def _reference_error(code: str, field: str, references: list[str]) -> dict[str, object]:
        return {
            "code": code,
            "message": f"{field} must reference exact existing task IDs.",
            "references": references,
        }
