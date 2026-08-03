from pathlib import Path
from typing import Any

from langgraph.types import interrupt
from sqlalchemy.orm import Session, sessionmaker

from app.agents.design_agent import DesignAgent
from app.agents.documentation_release_agent import DocumentationReleaseAgent
from app.agents.planning_agent import PlanningAgent
from app.agents.repository_coding_agent import RepositoryCodingAgent
from app.agents.requirement_agent import RequirementAgent
from app.agents.validation_agent import ValidationAgent
from app.core.time import utc_now
from app.orchestration.approvals import validate_approval_payload, validate_clarification_payload
from app.orchestration.planning_policy import PlanValidator, normalize_scenario_path_policy
from app.orchestration.replanning import mark_for_replanning
from app.orchestration.retries import RetryPolicy
from app.orchestration.rollback import perform_rollback
from app.orchestration.safe_stop import safe_stop_workflow
from app.orchestration.tasks import (
    all_required_tasks_completed,
    dependency_status,
    executable_plan,
    first_executable_task,
    mark_task_completed,
    satisfy_approved_design_tasks,
    unfinished_executable_task_ids,
)
from app.repositories.audit_repository import AuditRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.scenarios.url_shortener.contract import required_route_methods_from_requirement
from app.scenarios.url_shortener.validators import URLShortenerValidator
from app.schemas.agents.common import ApprovalGate
from app.services.approval_service import ApprovalService
from app.services.artifact_service import ArtifactService
from app.services.audit_service import AuditService
from app.tools.controlled_editor import ControlledEditor, file_sha256
from app.tools.git_tool import GitTool
from app.tools.models import StructuredEdit, ToolStatus
from app.tools.path_policy import PathPolicyError
from app.tools.repository_scanner import RepositoryScanner
from app.tools.test_runner import TestRunner
from app.tools.workspace_manager import WorkspaceManager


class WorkflowNodes:
    def __init__(
        self,
        *,
        sessions: sessionmaker[Session],
        requirement: RequirementAgent,
        design: DesignAgent,
        planning: PlanningAgent,
        repository_coding: RepositoryCodingAgent,
        validation: ValidationAgent,
        documentation: DocumentationReleaseAgent,
        approvals: ApprovalService,
        artifacts: ArtifactService,
        audit: AuditService,
        retry_policy: RetryPolicy,
        workspace: WorkspaceManager,
        scanner: RepositoryScanner,
        editor: ControlledEditor,
        git: GitTool,
        tests: TestRunner,
        target_validator: URLShortenerValidator,
    ) -> None:
        self.sessions = sessions
        self.requirement = requirement
        self.design = design
        self.planning = planning
        self.repository_coding = repository_coding
        self.validation = validation
        self.documentation = documentation
        self.approvals = approvals
        self.artifacts = artifacts
        self.audit = audit
        self.retry_policy = retry_policy
        self.workspace = workspace
        self.scanner = scanner
        self.editor = editor
        self.git = git
        self.tests = tests
        self.target_validator = target_validator

    def start(self, state: dict) -> dict:
        self.audit.record(state["workflow_id"], "WORKFLOW_STARTED", "START")
        return {
            "workflow_status": "RUNNING",
            "current_stage": "REQUIREMENTS",
            "updated_at": utc_now().isoformat(),
        }

    def requirement_agent(self, state: dict) -> dict:
        output = self.requirement.run(state)
        version = state.get("requirement_version", 1)
        with self.sessions.begin() as session:
            WorkflowRepository(session).add_requirement(
                state["workflow_id"], version, state["original_requirement"], output
            )
        return {
            "requirement_analysis": output,
            "current_stage": "REQUIREMENTS",
            "updated_at": utc_now().isoformat(),
        }

    def prepare_clarification(self, state: dict) -> dict:
        questions = state["requirement_analysis"].get("clarification_questions", [])
        with self.sessions.begin() as session:
            pending_payload, created = WorkflowRepository(session).prepare_clarification(
                state["workflow_id"],
                state.get("requirement_version", 1),
                state.get("state_version", 1),
                questions,
            )
            if created:
                AuditRepository(session).add(
                    state["workflow_id"],
                    "CLARIFICATION_REQUESTED",
                    "CLARIFICATION",
                    {
                        "clarification_id": pending_payload["clarificationId"],
                        "question_count": len(questions),
                        "state_version": pending_payload["stateVersion"],
                    },
                )
        pending = {"type": "CLARIFICATION", "payload": pending_payload}
        return {
            "pending_interaction": pending,
            "state_version": pending_payload["stateVersion"],
            "workflow_status": "WAITING_FOR_CLARIFICATION",
            "current_stage": "CLARIFICATION",
        }

    def clarification_gate(self, state: dict) -> dict:
        pending = state["pending_interaction"]
        pending_payload = pending["payload"]
        expected_version = pending_payload["stateVersion"]
        question_ids = [question["question_id"] for question in pending_payload["questions"]]
        response = interrupt(
            {
                "type": "CLARIFICATION",
                "workflowId": state["workflow_id"],
                "clarificationId": pending_payload["clarificationId"],
                "stateVersion": expected_version,
                "questions": pending_payload["questions"],
            }
        )
        answers = validate_clarification_payload(
            response,
            workflow_id=state["workflow_id"],
            clarification_id=pending_payload["clarificationId"],
            state_version=expected_version,
            question_ids=question_ids,
        )
        with self.sessions.begin() as session:
            completed_version, created = WorkflowRepository(session).complete_clarification(
                state["workflow_id"],
                state.get("requirement_version", 1),
                pending_payload["clarificationId"],
                expected_version,
                answers,
            )
            if created:
                AuditRepository(session).add(
                    state["workflow_id"],
                    "CLARIFICATION_SUBMITTED",
                    "CLARIFICATION",
                    {
                        "clarification_id": pending_payload["clarificationId"],
                        "answer_count": len(answers),
                        "state_version": completed_version,
                    },
                    actor_type="HUMAN",
                )
        clarification_ref = self.artifacts.write_markdown(
            state["workflow_id"],
            "CLARIFICATION_LOG",
            "02-clarification-log.md",
            {"answers": answers},
        )
        return {
            "clarification_answers": answers,
            "pending_interaction": {},
            "artifact_references": {
                **state.get("artifact_references", {}),
                "clarification_log": clarification_ref,
            },
            "state_version": completed_version,
            "workflow_status": "RUNNING",
            "current_stage": "REQUIREMENTS",
        }

    def prepare_requirement_approval(self, state: dict) -> dict:
        version = state.get("state_version", 1) + 1
        pending = self.approvals.request(state["workflow_id"], "REQUIREMENT", version)
        return {
            "pending_approval": pending,
            "state_version": version,
            "workflow_status": "WAITING_FOR_REQUIREMENT_APPROVAL",
            "current_stage": "REQUIREMENT_APPROVAL",
        }

    def requirement_approval_gate(self, state: dict) -> dict:
        return self._approval_gate(state, ApprovalGate.REQUIREMENT)

    def design_agent(self, state: dict) -> dict:
        try:
            output = self.design.run(state)
        except Exception as exc:
            return self._agent_failure(state, "design", "DESIGN", exc)
        version = state.get("architecture_version", 0) + 1
        self.audit.record(
            state["workflow_id"], "DESIGN_VERSION_CREATED", "DESIGN", {"version": version}
        )
        return {
            "architecture_design": output,
            "architecture_version": version,
            "workflow_status": "DESIGNING",
            "current_stage": "DESIGN",
            "last_error": {},
        }

    def design_validation(self, state: dict) -> dict:
        if state.get("architecture_design", {}).get("status") != "DESIGN_COMPLETE":
            return self._policy_error("INCONSISTENT_STATE", "The design is not complete.")
        return {}

    def planning_agent(self, state: dict) -> dict:
        scenario_path_policy = normalize_scenario_path_policy(
            state.get("scenario_profile", {})
        )
        output = self.planning.run(state)
        version = state.get("plan_version", 0) + 1
        self.audit.record(
            state["workflow_id"],
            "PLAN_VERSION_CREATED",
            "PLANNING",
            {
                "version": version,
                "attempt": state.get("retry_counts", {}).get("planning", 0) + 1,
            },
        )
        return {
            "implementation_plan": output,
            "scenario_path_policy": scenario_path_policy,
            "plan_version": version,
            "workflow_status": "PLANNING",
            "current_stage": "PLANNING",
            "last_error": {},
        }

    def plan_validation(self, state: dict) -> dict:
        plan = state.get("implementation_plan", {})
        policy = state.get("scenario_path_policy") or normalize_scenario_path_policy(
            state.get("scenario_profile", {})
        )
        result = PlanValidator().validate(
            plan,
            policy,
            approved_requirement=state.get("approved_requirement", {}),
            architecture_design=state.get("architecture_design", {}),
        )
        if not result.valid:
            retry_count = state.get("retry_counts", {}).get("planning", 0)
            attempt = retry_count + 1
            decision = self.retry_policy.decide("planning", retry_count, "PLANNING_FAILURE")
            retry_allowed = result.fixable and decision.allowed
            next_retry_count = decision.next_count if retry_allowed else retry_count
            task_ids = [task.get("task_id") for task in plan.get("tasks", [])]
            details = {
                "attempt": attempt,
                "generated_task_ids": task_ids,
                "execution_order": list(plan.get("execution_order", [])),
                "validation_errors": list(result.errors),
                "correctable": result.fixable,
            }
            with self.sessions.begin() as session:
                repository = WorkflowRepository(session)
                repository.update_state(
                    state["workflow_id"],
                    {
                        "workflow_status": "RETRYING" if retry_allowed else "FAILED",
                        "current_stage": "PLANNING",
                        "state_version": state.get("state_version", 1),
                    },
                )
                audits = AuditRepository(session)
                audits.add(
                    state["workflow_id"], "PLAN_VALIDATION_FAILED", "PLANNING", details
                )
                if retry_allowed:
                    audits.add(
                        state["workflow_id"],
                        "PLAN_CORRECTION_STARTED",
                        "PLANNING",
                        {
                            "failed_attempt": attempt,
                            "correction_attempt": next_retry_count + 1,
                            "validation_errors": list(result.errors),
                        },
                    )
            error = {
                "code": "PLAN_NOT_EXECUTABLE",
                "category": "PLANNING_FAILURE",
                "message": "The implementation plan requires correction.",
                "retry_allowed": retry_allowed,
                "details": {
                    **details,
                    "retry_exhausted": result.fixable and not retry_allowed,
                },
            }
            return {
                "planning_validation_errors": list(result.errors),
                "planning_correction_context": details,
                "retry_counts": {
                    **state.get("retry_counts", {}),
                    "planning": next_retry_count,
                },
                "workflow_status": "RETRYING" if retry_allowed else "FAILED",
                "current_stage": "PLANNING",
                "last_error": error,
            }

        retry_count = state.get("retry_counts", {}).get("planning", 0)
        with self.sessions.begin() as session:
            WorkflowRepository(session).replace_tasks(state["workflow_id"], plan)
            if retry_count:
                AuditRepository(session).add(
                    state["workflow_id"],
                    "PLAN_CORRECTION_COMPLETED",
                    "PLANNING",
                    {"attempt": retry_count + 1, "retry_count": retry_count},
                )
        return {
            "planning_validation_errors": [],
            "planning_correction_context": {},
            "workflow_status": "PLANNING",
            "current_stage": "PLANNING",
            "last_error": {},
        }

    def prepare_architecture_approval(self, state: dict) -> dict:
        version = state.get("state_version", 1) + 1
        pending = self.approvals.request(state["workflow_id"], "ARCHITECTURE_AND_PLAN", version)
        return {
            "pending_approval": pending,
            "state_version": version,
            "workflow_status": "WAITING_FOR_ARCHITECTURE_APPROVAL",
            "current_stage": "ARCHITECTURE_APPROVAL",
        }

    def architecture_approval_gate(self, state: dict) -> dict:
        result = self._approval_gate(state, ApprovalGate.ARCHITECTURE_AND_PLAN)
        if result.get("last_approval_action") not in {"APPROVE", "APPROVE_WITH_CONDITIONS"}:
            return result
        plan, satisfied_task_ids = satisfy_approved_design_tasks(
            state.get("implementation_plan", {})
        )
        if satisfied_task_ids:
            with self.sessions.begin() as session:
                WorkflowRepository(session).mark_tasks_completed(
                    state["workflow_id"], satisfied_task_ids
                )
                audits = AuditRepository(session)
                for task_id in satisfied_task_ids:
                    audits.add(
                        state["workflow_id"],
                        "TASK_SATISFIED",
                        "ARCHITECTURE_APPROVAL",
                        {
                            "task_id": task_id,
                            "source": "ARCHITECTURE_AND_PLAN_APPROVAL",
                        },
                    )
        return {
            **result,
            "implementation_plan": plan,
            "satisfied_task_ids": sorted(
                set([*state.get("satisfied_task_ids", []), *satisfied_task_ids])
            ),
        }

    def workspace_setup(self, state: dict) -> dict:
        if state.get("scenario_type") in {"BROWNFIELD", "AMBIGUOUS"}:
            return self._brownfield_workspace_setup(state)
        created = self.workspace.create_workspace(state["workspace_name"])
        if created.status != ToolStatus.SUCCESS or not created.created:
            return self._policy_error("WORKSPACE_CONFLICT", "The target workspace is not empty.")
        repository = self.workspace.get_workspace(state["workspace_name"])
        initialized = self.git.initialize_repository(repository)
        if initialized.status != ToolStatus.SUCCESS:
            return self._policy_error(
                "REPOSITORY_INITIALIZATION_FAILED", "Git initialization failed."
            )
        baseline = StructuredEdit(
            operation="CREATE",
            relative_path="README.md",
            content=(
                f"# {state['workspace_name']}\n\nWorkflow ID: {state['workflow_id']}\n\n"
                "Generated through governed workflow\n"
            ),
        )
        applied = self.editor.apply_batch(repository, [baseline])
        if applied.status != ToolStatus.SUCCESS:
            return self._policy_error("BASELINE_WRITE_FAILED", "The baseline could not be written.")
        self.git.stage_files(repository, ["README.md"])
        committed = self.git.commit(repository, "Create governed workflow baseline")
        if committed.status != ToolStatus.SUCCESS or not committed.commit_id:
            return self._policy_error(
                "BASELINE_COMMIT_FAILED", "The baseline could not be committed."
            )
        branch = f"agent/{state['workflow_id'].lower()}-{state['workspace_name'].lower()}"
        branched = self.git.create_branch(repository, branch)
        if branched.status != ToolStatus.SUCCESS:
            return self._policy_error(
                "BRANCH_CREATE_FAILED", "The working branch could not be created."
            )
        for event in (
            "WORKSPACE_CREATED",
            "GIT_REPOSITORY_INITIALIZED",
            "GIT_BASELINE_CREATED",
            "GIT_BRANCH_CREATED",
        ):
            self.audit.record(state["workflow_id"], event, "WORKSPACE")
        return {
            "repository_path": str(repository),
            "baseline_commit": committed.commit_id,
            "working_branch": branch,
            "current_commit": committed.commit_id,
            "workflow_status": "INITIALIZING_WORKSPACE",
            "current_stage": "WORKSPACE",
        }

    def _brownfield_workspace_setup(self, state: dict) -> dict:
        source_name = state.get("source_workspace", "")
        destination_name = state["workspace_name"]
        try:
            self.workspace.validate_brownfield_source(source_name, destination_name)
        except PathPolicyError as exc:
            return self._policy_error(exc.error_code, "The Brownfield source is invalid.")
        self.audit.record(
            state["workflow_id"],
            "BROWNFIELD_SOURCE_VALIDATED",
            "WORKSPACE",
            {"source_workspace": source_name, "destination_workspace": destination_name},
        )
        copied = self.workspace.copy_brownfield_workspace(source_name, destination_name)
        if copied.status != ToolStatus.SUCCESS:
            code = copied.error.code if copied.error else "WORKSPACE_COPY_FAILED"
            return self._policy_error(code, "The Brownfield baseline could not be copied.")
        self.audit.record(
            state["workflow_id"],
            "BROWNFIELD_WORKSPACE_COPIED",
            "WORKSPACE",
            {"source_workspace": source_name, "destination_workspace": destination_name},
        )
        repository = self.workspace.get_workspace(destination_name)
        initialized = self.git.initialize_repository(repository)
        if initialized.status != ToolStatus.SUCCESS:
            return self._policy_error(
                "REPOSITORY_INITIALIZATION_FAILED", "Git initialization failed."
            )
        baseline_files = self.scanner.list_files(repository)
        staged = self.git.stage_files(repository, baseline_files)
        if staged.status != ToolStatus.SUCCESS:
            return self._policy_error(
                "BASELINE_STAGE_FAILED", "The Brownfield baseline could not be staged."
            )
        committed = self.git.commit(repository, "Create governed Brownfield baseline")
        if committed.status != ToolStatus.SUCCESS or not committed.commit_id:
            return self._policy_error(
                "BASELINE_COMMIT_FAILED", "The Brownfield baseline could not be committed."
            )
        remotes = self.git.get_remotes(repository)
        if remotes.status != ToolStatus.SUCCESS or remotes.stdout.strip():
            return self._policy_error(
                "GIT_REMOTE_PRESENT", "The Brownfield destination must not have a Git remote."
            )
        self.audit.record(
            state["workflow_id"],
            "BROWNFIELD_BASELINE_CREATED",
            "WORKSPACE",
            {"file_count": len(baseline_files)},
        )
        branch = f"agent/{state['workflow_id'].lower()}-{destination_name.lower()}"
        branched = self.git.create_branch(repository, branch)
        if branched.status != ToolStatus.SUCCESS:
            return self._policy_error(
                "BRANCH_CREATE_FAILED", "The Brownfield branch could not be created."
            )
        self.audit.record(
            state["workflow_id"],
            "BROWNFIELD_BRANCH_CREATED",
            "WORKSPACE",
            {"branch": branch},
        )
        return {
            "repository_path": str(repository),
            "baseline_commit": committed.commit_id,
            "working_branch": branch,
            "current_commit": committed.commit_id,
            "workflow_status": "INITIALIZING_WORKSPACE",
            "current_stage": "WORKSPACE",
        }

    def repository_analysis(self, state: dict) -> dict:
        repository = Path(state["repository_path"])
        scan = self.scanner.scan(repository).model_dump(mode="json")
        if state.get("scenario_type") in {"BROWNFIELD", "AMBIGUOUS"}:
            relevant_files: list[dict[str, str]] = []
            for relative_path in self.scanner.list_files(repository):
                path = repository / relative_path
                if path.suffix.lower() not in {
                    ".py",
                    ".md",
                    ".toml",
                    ".ini",
                    ".txt",
                    ".mako",
                }:
                    continue
                try:
                    content = self.scanner.read_safe_text_file(repository, relative_path)
                except PathPolicyError:
                    continue
                relevant_files.append(
                    {
                        "relative_path": relative_path,
                        "content": content,
                        "sha256": file_sha256(path),
                    }
                )
            scan.update(
                {
                    "source_workspace": state.get("source_workspace", ""),
                    "destination_workspace": state.get("workspace_name", ""),
                    "repository_tree": self.scanner.list_files(repository),
                    "relevant_files": relevant_files,
                    "git_baseline": {
                        "commit": state.get("baseline_commit", ""),
                        "branch": state.get("working_branch", ""),
                    },
                }
            )
        scan_ref = self.artifacts.write_json(
            state["workflow_id"], "REPOSITORY_SCAN", "repository-scan.json", scan
        )
        if scan.get("restricted_files_found"):
            return {
                "repository_scan": scan,
                "last_error": {
                    "code": "REPOSITORY_POLICY_VIOLATION",
                    "category": "POLICY_VIOLATION",
                    "message": "Restricted paths were detected.",
                },
            }
        analysis = self.repository_coding.analyze(state, scan)
        return {
            "repository_scan": scan,
            "repository_analysis": analysis,
            "artifact_references": {
                **state.get("artifact_references", {}),
                "repository_scan": scan_ref,
            },
            "workflow_status": "ANALYZING_REPOSITORY",
            "current_stage": "REPOSITORY_ANALYSIS",
        }

    def repository_policy_validation(self, state: dict) -> dict:
        return {}

    def git_checkpoint(self, state: dict) -> dict:
        if not state.get("baseline_commit") or not state.get("working_branch"):
            return self._policy_error("INCONSISTENT_STATE", "The Git checkpoint is incomplete.")
        return {}

    def coding_agent(self, state: dict) -> dict:
        repository = Path(state["repository_path"])
        plan = state.get("implementation_plan", {})
        retry_context = state.get("retry_context", {})
        retry_task = retry_context.get("originating_task")
        active_task = retry_task if retry_context.get("active") and retry_task else None
        active_task = active_task or first_executable_task(plan)
        if active_task is None:
            unfinished = unfinished_executable_task_ids(plan)
            if unfinished:
                return self._policy_error(
                    "TASK_DEPENDENCY_VIOLATION",
                    "No unfinished task has satisfied dependencies.",
                    {
                        "unfinished_task_ids": unfinished,
                        "dependency_status": "BLOCKED",
                    },
                )
            return self._policy_error(
                "NO_EXECUTABLE_TASK", "No unfinished executable task is available."
            )
        dependencies = dependency_status(plan, active_task)
        if dependencies["status"] != "READY":
            return self._policy_error(
                "TASK_DEPENDENCY_VIOLATION",
                "The selected task has incomplete dependencies.",
                {
                    "task_id": active_task.get("task_id"),
                    **dependencies,
                },
            )
        repository_context = self._coding_repository_context(state, repository, active_task)
        hashes = {
            item["relative_path"]: item["sha256"] for item in repository_context
        }
        selection_evidence = {
            "task_id": active_task["task_id"],
            "task_type": active_task.get("task_type", ""),
            "dependency_status": dependencies["status"],
            "dependencies": dependencies["dependencies"],
            "incomplete_dependencies": dependencies["incomplete_dependencies"],
            "originating_task_id": retry_context.get("originating_task_id"),
            "retry_task_id": retry_context.get("retry_task_id"),
        }
        self.audit.record(
            state["workflow_id"], "CODING_TASK_SELECTED", "CODING", selection_evidence
        )
        coding_state = {
            **state,
            "implementation_plan": executable_plan(plan),
            "active_task": active_task,
            "repository_context": repository_context,
        }
        output = self.repository_coding.code(coding_state, hashes)
        attempt_number = int(
            retry_context.get("attempt_number")
            or state.get("retry_counts", {}).get("coding", 0) + 1
        )
        coding_attempt = {
            "task_id": active_task.get("task_id"),
            "attempt_number": attempt_number,
            "originating_task_id": (
                retry_context.get("originating_task_id") or active_task.get("task_id")
            ),
            "retry_task_id": retry_context.get("retry_task_id"),
            "applied": False,
        }
        self.audit.record(
            state["workflow_id"],
            "CHANGE_PLAN_CREATED",
            "CODING",
            {"edit_count": len(output["structured_edits"]), **selection_evidence},
        )
        return {
            "active_task": active_task,
            "code_change_plan": output,
            "coding_attempt": coding_attempt,
            "implementation_result": {},
            "task_validation_result": {},
            "validation_result": {},
            "workflow_status": "IMPLEMENTING",
            "current_stage": "CODING",
            "last_error": {},
        }

    def _coding_repository_context(
        self, state: dict, repository: Path, active_task: dict
    ) -> list[dict[str, str]]:
        """Read current allowlisted files needed for every coding attempt."""
        policy = self.editor.path_policy
        task_allowed = list(active_task.get("allowed_paths", []))
        scenario_profile = state.get("scenario_profile", {})
        effective_allowed = policy.resolve_effective_allowed_paths(
            task_allowed,
            list(scenario_profile.get("allowed_paths", [])),
            policy_mode=scenario_profile.get("path_policy_mode"),
        )
        names = set(map(str, active_task.get("expected_files", [])))
        for allowed in effective_allowed:
            try:
                candidate = policy.validate_relative_path(
                    repository, allowed, operation="write"
                )
            except PathPolicyError:
                continue
            if candidate.is_file():
                names.add(allowed)
            elif candidate.is_dir():
                for nested in candidate.rglob("*"):
                    if nested.is_file():
                        names.add(nested.relative_to(repository).as_posix())
        if state.get("retry_context", {}).get("active"):
            names.update(
                item.get("relative_path", "")
                for item in state.get("code_change_plan", {}).get("structured_edits", [])
            )
            names.update(state.get("changed_files", []))
        context: list[dict[str, str]] = []
        for name in sorted(names):
            if not name:
                continue
            try:
                normalized = policy.validate_allowed_path(name, effective_allowed)
                candidate = policy.validate_relative_path(repository, normalized)
            except PathPolicyError:
                continue
            if not candidate.is_file() or candidate.stat().st_size > self.editor.max_file_bytes:
                continue
            try:
                content = candidate.read_bytes().decode("utf-8")
            except (OSError, UnicodeError):
                continue
            context.append(
                {
                    "relative_path": normalized,
                    "sha256": file_sha256(candidate),
                    "content": content,
                }
            )
        return context

    def change_policy_validation(self, state: dict) -> dict:
        edits = [
            StructuredEdit.model_validate(item)
            for item in state["code_change_plan"]["structured_edits"]
        ]
        contexts, error = self._resolve_edit_policy_contexts(state, edits)
        if error is not None:
            return error
        return {"edit_policy_contexts": contexts}

    @staticmethod
    def _policy_path_evidence(policy, paths: list[str]) -> list[str]:
        evidence: list[str] = []
        for path in paths:
            try:
                evidence.append(policy.normalize_policy_path(path))
            except PathPolicyError:
                safe_name = Path(path.replace("\\", "/")).name
                if safe_name:
                    evidence.append(safe_name)
        return sorted(set(evidence))
    def _resolve_edit_policy_contexts(
        self, state: dict, edits: list[StructuredEdit]
    ) -> tuple[list[dict[str, object]], dict | None]:
        policy = self.editor.path_policy
        tasks = {
            task["task_id"]: task
            for task in state.get("implementation_plan", {}).get("tasks", [])
        }
        scenario_allowed = list(state.get("scenario_profile", {}).get("allowed_paths", []))
        scenario_policy_mode = state.get("scenario_profile", {}).get("path_policy_mode")
        change_plan = state.get("code_change_plan", {}).get("change_plan", [])
        contexts: list[dict[str, object]] = []
        for edit in edits:
            task_id = None
            normalized_path = None
            try:
                normalized_path = policy.normalize_relative_path(edit.relative_path)
                for item in change_plan:
                    mapped_paths = [
                        policy.normalize_relative_path(path) for path in item.get("paths", [])
                    ]
                    if normalized_path in mapped_paths:
                        task_id = item.get("task_id")
                        break
                task = tasks.get(task_id)
                if task is None:
                    raise PathPolicyError(
                        "The edit is not mapped to an approved task.",
                        "REPOSITORY_POLICY_VIOLATION",
                        details={"policy_rule": "CHANGE_PLAN_TASK_MAPPING"},
                    )
                if str(task.get("status", "PLANNED")).upper() in {"COMPLETED", "SATISFIED"}:
                    raise PathPolicyError(
                        "The approved task is already satisfied.",
                        "REPOSITORY_POLICY_VIOLATION",
                        details={"policy_rule": "COMPLETED_TASK_BLOCKED"},
                    )
                task_allowed = list(task.get("allowed_paths", []))
                effective = policy.resolve_effective_allowed_paths(
                    task_allowed,
                    scenario_allowed,
                    policy_mode=scenario_policy_mode,
                )
                context: dict[str, object] = {
                    "attempted_path": normalized_path,
                    "normalized_path": normalized_path,
                    "task_id": task_id,
                    "task_allowed_paths": policy.normalize_policy_paths(task_allowed),
                    "scenario_allowed_paths": policy.normalize_policy_paths(scenario_allowed),
                    "effective_allowed_paths": effective,
                    "policy_rule": "EFFECTIVE_ALLOWED_PATHS",
                }
                policy.validate_allowed_path(edit.relative_path, effective)
                contexts.append(context)
            except PathPolicyError as exc:
                safe_path = normalized_path or Path(
                    edit.relative_path.replace("\\", "/")
                ).name
                task = tasks.get(task_id, {})
                details = {
                    "attempted_path": safe_path,
                    "normalized_path": safe_path,
                    "task_id": task_id or state.get("active_task", {}).get("task_id"),
                    "task_allowed_paths": self._policy_path_evidence(
                        policy, list(task.get("allowed_paths", []))
                    ),
                    "scenario_allowed_paths": self._policy_path_evidence(
                        policy, scenario_allowed
                    ),
                    "effective_allowed_paths": [],
                    "policy_rule": f"GLOBAL_WORKSPACE_SAFETY:{exc.error_code}",
                    **exc.details,
                }
                return [], self._policy_error(
                    "REPOSITORY_POLICY_VIOLATION",
                    "An edit path was not approved.",
                    details,
                )
        return contexts, None
    def prepare_high_risk_approval(self, state: dict) -> dict:
        version = state.get("state_version", 1) + 1
        pending = self.approvals.request(state["workflow_id"], "HIGH_RISK_CHANGE", version)
        return {
            "pending_approval": pending,
            "state_version": version,
            "workflow_status": "WAITING_FOR_ARCHITECTURE_APPROVAL",
            "current_stage": "HIGH_RISK_CHANGE_APPROVAL",
        }

    def high_risk_approval_gate(self, state: dict) -> dict:
        return self._approval_gate(state, ApprovalGate.HIGH_RISK_CHANGE)

    def apply_changes(self, state: dict) -> dict:
        edits = [
            StructuredEdit.model_validate(item)
            for item in state["code_change_plan"]["structured_edits"]
        ]
        if not edits:
            self.audit.record(
                state["workflow_id"],
                "CHANGES_APPLIED",
                "CODING",
                {"changed_files": [], "task_id": state.get("active_task", {}).get("task_id")},
            )
            return {
                "implementation_result": state["code_change_plan"],
                "coding_attempt": {
                    **state.get("coding_attempt", {}),
                    "applied": True,
                    "applied_change_count": 0,
                    "changed_files": [],
                },
                "last_error": {},
            }
        contexts = state.get("edit_policy_contexts", [])
        if len(contexts) != len(edits):
            contexts, error = self._resolve_edit_policy_contexts(state, edits)
            if error is not None:
                return error
        allowed = sorted(
            {
                path
                for context in contexts
                for path in context.get("effective_allowed_paths", [])
            }
        )
        repository = Path(state["repository_path"])
        result = self.editor.apply_batch(
            repository,
            edits,
            allowed_paths=allowed,
            policy_context=contexts[0] if len(contexts) == 1 else None,
        )
        if result.status != ToolStatus.SUCCESS:
            code = result.error.code if result.error else "EDIT_FAILED"
            details = result.error.details if result.error else {}
            category = (
                "REPOSITORY_POLICY_VIOLATION"
                if code == "REPOSITORY_POLICY_VIOLATION"
                else str(details.get("failure_category") or code)
            )
            return self._state_error(code, category, "A controlled edit was blocked.", details)
        changed = [operation.path for operation in result.operations]
        diff = self.git.get_diff(repository)
        diff_ref = self.artifacts.write_text(
            state["workflow_id"], "GIT_DIFF", "changes.diff", diff.stdout
        )
        staged = self.git.stage_files(repository, changed)
        committed = self.git.commit(
            repository,
            f"Apply governed change attempt {state.get('retry_counts', {}).get('coding', 0) + 1}",
        )
        if staged.status != ToolStatus.SUCCESS or committed.status != ToolStatus.SUCCESS:
            return self._policy_error("GIT_CHECKPOINT_FAILED", "The change checkpoint failed.")
        self.audit.record(
            state["workflow_id"],
            "CHANGES_APPLIED",
            "CODING",
            {
                "changed_files": changed,
                "task_id": state.get("active_task", {}).get("task_id"),
                "attempt_number": state.get("coding_attempt", {}).get("attempt_number"),
                "originating_task_id": state.get("coding_attempt", {}).get(
                    "originating_task_id"
                ),
                "retry_task_id": state.get("coding_attempt", {}).get("retry_task_id"),
            },
        )
        implementation_ref = self.artifacts.write_markdown(
            state["workflow_id"],
            "IMPLEMENTATION_SUMMARY",
            "08-implementation-summary.md",
            state["code_change_plan"],
            [diff_ref],
        )
        change_summary_ref = self.artifacts.write_markdown(
            state["workflow_id"],
            "LOCAL_CHANGE_SUMMARY",
            "11-pr-summary.md",
            {"changed_files": changed, "commit": committed.commit_id},
            [diff_ref],
        )
        return {
            "implementation_result": state["code_change_plan"],
                "coding_attempt": {
                    **state.get("coding_attempt", {}),
                    "applied": True,
                    "applied_change_count": len(changed),
                    "changed_files": changed,
                },
            "changed_files": sorted(set([*state.get("changed_files", []), *changed])),
            "current_commit": committed.commit_id or "",
            "git_diff_artifact": diff_ref,
            "last_error": {},
            "artifact_references": {
                **state.get("artifact_references", {}),
                "git_diff": diff_ref,
                "implementation_summary": implementation_ref,
                "change_summary": change_summary_ref,
            },
        }

    def policy_validation(self, state: dict) -> dict:
        return {}

    def task_validation(self, state: dict) -> dict:
        task = state.get("active_task", {})
        task_id = task.get("task_id")
        attempt = state.get("coding_attempt", {})
        commands = [str(item) for item in task.get("validation_commands", [])]
        resolved_import_modules = self.tests.task_import_modules(
            task, list(attempt.get("changed_files", []))
        )
        import_modules = (
            None
            if str(task.get("task_type", "")) == "VALIDATION"
            else resolved_import_modules
        )
        self.audit.record(
            state["workflow_id"],
            "TASK_VALIDATION_STARTED",
            "TASK_VALIDATION",
            {
                "task_id": task_id,
                "validation_commands": commands,
                "attempt_number": attempt.get("attempt_number"),
                "originating_task_id": attempt.get("originating_task_id"),
                "retry_task_id": attempt.get("retry_task_id"),
                "import_modules": ["app.main"] if import_modules is None else import_modules,
            },
        )
        command_results = self.tests.run_task_commands(
            Path(state["repository_path"]),
            commands,
            import_modules=import_modules,
        )
        passed = all(result.status == ToolStatus.SUCCESS for result in command_results)
        failed = next(
            (result for result in command_results if result.status != ToolStatus.SUCCESS), None
        )
        result = {
            "level": "TASK",
            "task_id": task_id,
            "attempt_number": attempt.get("attempt_number"),
            "originating_task_id": attempt.get("originating_task_id"),
            "retry_task_id": attempt.get("retry_task_id"),
            "applied": bool(attempt.get("applied")),
            "status": "VALIDATION_PASSED" if passed else "VALIDATION_FAILED",
            "failure_category": None if passed else "IMPLEMENTATION_DEFECT",
            "command_results": [item.model_dump(mode="json") for item in command_results],
            "failed_command": failed.command_id if failed else None,
            "relevant_output": (
                {"stdout": failed.stdout, "stderr": failed.stderr} if failed else {}
            ),
        }
        self.audit.record(
            state["workflow_id"],
            "TASK_VALIDATION_COMPLETED",
            "TASK_VALIDATION",
            {
                "task_id": task_id,
                "status": result["status"],
                "failed_command": result["failed_command"],
                "attempt_number": result["attempt_number"],
                "originating_task_id": result["originating_task_id"],
                "retry_task_id": result["retry_task_id"],
            },
        )
        return {"task_validation_result": result, "validation_result": result}

    def complete_task(self, state: dict) -> dict:
        task = state.get("active_task", {})
        task_id = str(task.get("task_id", ""))
        plan, _ = mark_task_completed(state.get("implementation_plan", {}), task_id)
        with self.sessions.begin() as session:
            repository = WorkflowRepository(session)
            completed = repository.mark_tasks_completed(state["workflow_id"], [task_id])
            if completed:
                AuditRepository(session).add(
                    state["workflow_id"],
                    "TASK_COMPLETED",
                    "CODING",
                    {
                        "task_id": task_id,
                        "task_type": task.get("task_type"),
                        "validation_commands": task.get("validation_commands", []),
                    },
                )
        complete = all_required_tasks_completed(plan)
        return {
            "implementation_plan": plan,
            "active_task": {**task, "status": "COMPLETED"},
            "all_required_tasks_completed": complete,
            "retry_context": {},
            "last_error": {},
            "workflow_status": "VALIDATING" if complete else "IMPLEMENTING",
            "current_stage": "FINAL_VALIDATION" if complete else "CODING",
        }

    def parallel_start(self, state: dict) -> dict:
        if not all_required_tasks_completed(state.get("implementation_plan", {})):
            return self._state_error(
                "INCOMPLETE_IMPLEMENTATION",
                "INCOMPLETE_IMPLEMENTATION",
                "Final validation requires every executable task to be complete.",
                {
                    "unfinished_task_ids": unfinished_executable_task_ids(
                        state.get("implementation_plan", {})
                    )
                },
            )
        return {
            "workflow_status": "VALIDATING",
            "current_stage": "FINAL_VALIDATION",
            "all_required_tasks_completed": True,
        }

    def validation_agent(self, state: dict) -> dict:
        if not all_required_tasks_completed(state.get("implementation_plan", {})):
            return {
                "validation_result": {
                    "status": "INCOMPLETE_IMPLEMENTATION",
                    "failure_category": "INCOMPLETE_IMPLEMENTATION",
                    "unfinished_task_ids": unfinished_executable_task_ids(
                        state.get("implementation_plan", {})
                    ),
                },
                "validation_branch_complete": True,
            }
        self.audit.record(state["workflow_id"], "VALIDATION_STARTED", "VALIDATION")
        suite = self.tests.run_validation_suite(Path(state["repository_path"]))
        results = [suite.ruff.model_dump(mode="json")]
        if suite.pytest is not None:
            results.append(suite.pytest.model_dump(mode="json"))
        contract_payload = {
            "profile_id": state.get("scenario_profile", {}).get("profile_id", "GENERIC"),
            "status": "NOT_APPLICABLE",
            "reason": "No specialized target contract applies.",
        }
        if contract_payload["profile_id"] in {
            "URL_SHORTENER_GREENFIELD",
            "URL_SHORTENER_BROWNFIELD",
            "URL_SHORTENER_AMBIGUOUS_ALIASES",
        }:
            if state.get("execution_mode") == "OPENAI":
                contract_payload = self.target_validator.validate(
                    Path(state["repository_path"]),
                    required_route_methods_from_requirement(
                        state.get("original_requirement", "")
                    ),
                ).model_dump(mode="json")
                results.append(
                    {
                        "command_id": "URL_SHORTENER_CONTRACT",
                        "status": ("SUCCESS" if contract_payload["status"] == "PASS" else "FAILED"),
                        "evidence": contract_payload,
                    }
                )
            else:
                contract_payload = {
                    "profile_id": contract_payload["profile_id"],
                    "status": "NOT_EXECUTED",
                    "reason": "SCRIPTED_PLATFORM_TEST_DOUBLE",
                }
        contract_ref = self.artifacts.write_json(
            state["workflow_id"],
            "TARGET_CONTRACT_EVIDENCE",
            "09-target-contract-evidence.json",
            contract_payload,
        )
        output = self.validation.run(state, results)
        output = self._normalize_final_validation(state, output, contract_payload)
        self.audit.record(
            state["workflow_id"],
            "VALIDATION_COMPLETED",
            "VALIDATION",
            {"status": output["status"], "failure_category": output.get("failure_category")},
        )
        quality_ref = self.artifacts.write_markdown(
            state["workflow_id"],
            "QUALITY_SECURITY_REVIEW",
            "10-quality-security-review.md",
            output,
        )
        return {
            "validation_result": output,
            "target_contract_evidence": contract_payload,
            "validation_branch_complete": True,
            "artifact_references": {
                **state.get("artifact_references", {}),
                "quality_review": quality_ref,
                "target_contract_evidence": contract_ref,
            },
        }

    @staticmethod
    def _normalize_final_validation(
        state: dict, output: dict, contract_payload: dict
    ) -> dict:
        """Require explicit evidence for every approved acceptance criterion."""
        normalized = dict(output)
        approved = list(state.get("approved_requirement", {}).get("acceptance_criteria", []))
        reported = {
            str(item.get("criterion")): dict(item)
            for item in normalized.get("acceptance_criteria_results", [])
        }
        contract_failed = contract_payload.get("status") == "FAIL"
        complete_results: list[dict] = []
        for criterion in approved:
            item = reported.get(str(criterion))
            if item is None:
                status = "NOT_IMPLEMENTED" if contract_failed else "NOT_TESTED"
                item = {
                    "criterion": criterion,
                    "status": status,
                    "evidence": ["No complete validation evidence was supplied."],
                }
            complete_results.append(item)
        if approved:
            normalized["acceptance_criteria_results"] = complete_results
        unsuccessful = {
            item.get("status")
            for item in normalized.get("acceptance_criteria_results", [])
        } & {"FAILED", "NOT_IMPLEMENTED", "NOT_TESTED"}
        if contract_failed or unsuccessful:
            normalized["architecture_compliance"] = False
            normalized["status"] = "VALIDATION_FAILED"
            normalized["release_recommendation"] = "NOT_READY"
            normalized["retry_recommended"] = not contract_failed
            normalized["replan_recommended"] = contract_failed
            normalized["failure_category"] = (
                "ARCHITECTURE_MISMATCH" if contract_failed else "IMPLEMENTATION_DEFECT"
            )
        return normalized

    def documentation_draft(self, state: dict) -> dict:
        return {
            "documentation_draft": self.documentation.draft(state),
            "documentation_branch_complete": True,
        }

    def validation_join(self, state: dict) -> dict:
        return {
            "parallel_join_complete": bool(
                state.get("validation_branch_complete")
                and state.get("documentation_branch_complete")
            )
        }

    def failure_classifier(self, state: dict) -> dict:
        category = state.get("validation_result", {}).get("failure_category") or state.get(
            "last_error", {}
        ).get("category")
        return {"last_error": {"category": category}} if category else {}

    def retry_router(self, state: dict) -> dict:
        current = state.get("retry_counts", {}).get("coding", 0)
        validation = state.get("task_validation_result", {})
        attempt = state.get("coding_attempt", {})
        current_validation = (
            validation.get("status") == "VALIDATION_FAILED"
            and validation.get("task_id") == attempt.get("task_id")
            and validation.get("attempt_number") == attempt.get("attempt_number")
            and validation.get("retry_task_id") == attempt.get("retry_task_id")
            and validation.get("applied") is True
            and attempt.get("applied") is True
        )
        if not current_validation:
            return {
                "retry_counts": dict(state.get("retry_counts", {})),
                "last_error": {
                    **state.get("last_error", {}),
                    "retry_allowed": False,
                },
                "retry_context": {},
                "workflow_status": "FAILED",
                "current_stage": "CODING",
            }
        category = validation.get("failure_category")
        decision = self.retry_policy.decide("coding", current, category)
        counts = {**state.get("retry_counts", {}), "coding": decision.next_count}
        originating_task = state.get("active_task", {})
        failed_command = validation.get("failed_command") if current_validation else None
        retry_task_id = (
            f"{originating_task.get('task_id', 'TASK')}-RETRY-{decision.next_count}"
            if decision.allowed
            else None
        )
        if decision.allowed:
            self.audit.record(
                state["workflow_id"],
                "RETRY_STARTED",
                "CODING",
                {
                    "retry": decision.next_count,
                    "originating_task_id": originating_task.get("task_id"),
                    "retry_task_id": retry_task_id,
                    "validation_command": failed_command,
                    "failure_category": category,
                    "attempt_number": decision.next_count + 1,
                },
            )
        return {
            "retry_counts": counts,
            "last_error": {"category": category, "retry_allowed": decision.allowed},
            "retry_context": {
                "active": decision.allowed,
                "originating_task": originating_task,
                "originating_task_id": originating_task.get("task_id"),
                "retry_task_id": retry_task_id,
                "validation_command": failed_command,
                "failure_category": category,
                "attempt_number": decision.next_count + 1,
            },
            "workflow_status": "RETRYING",
            "current_stage": "CODING",
        }

    def replan(self, state: dict) -> dict:
        category = state.get("validation_result", {}).get("failure_category")
        level = "REQUIREMENT" if category == "REQUIREMENT_AMBIGUITY" else "DESIGN"
        self.audit.record(state["workflow_id"], "REPLAN_STARTED", "REPLAN", {"level": level})
        return mark_for_replanning(state, level, f"Validation category: {category}")

    def rollback(self, state: dict) -> dict:
        return perform_rollback(state, self.git, self.artifacts, self.audit)

    def safe_stop(self, state: dict) -> dict:
        return safe_stop_workflow(state, self.artifacts, self.audit)

    def documentation_release_agent(self, state: dict) -> dict:
        if not all_required_tasks_completed(state.get("implementation_plan", {})):
            return self._state_error(
                "INCOMPLETE_IMPLEMENTATION",
                "INCOMPLETE_IMPLEMENTATION",
                "Release processing requires every executable task to be complete.",
                {
                    "unfinished_task_ids": unfinished_executable_task_ids(
                        state.get("implementation_plan", {})
                    )
                },
            )
        output = self.documentation.release(state)
        self.audit.record(
            state["workflow_id"],
            "RELEASE_RECOMMENDATION_CREATED",
            "RELEASE",
            {"status": output["recommended_status"]},
        )
        return {"release_package": output, "current_stage": "RELEASE_DOCUMENTATION"}

    def prepare_release_approval(self, state: dict) -> dict:
        version = state.get("state_version", 1) + 1
        pending = self.approvals.request(state["workflow_id"], "RELEASE", version)
        return {
            "pending_approval": pending,
            "state_version": version,
            "workflow_status": "WAITING_FOR_RELEASE_APPROVAL",
            "current_stage": "RELEASE_APPROVAL",
        }

    def release_approval_gate(self, state: dict) -> dict:
        result = self._approval_gate(state, ApprovalGate.RELEASE)
        if result.get("last_approval_action") == "REQUEST_CHANGES":
            result.update(mark_for_replanning(state, "PLAN", "Release changes requested."))
        return result

    def finalize_ready(self, state: dict) -> dict:
        return self._finalize(state, "READY")

    def finalize_not_ready(self, state: dict) -> dict:
        return self._finalize(state, "NOT_READY")

    def finalize_ready_with_conditions(self, state: dict) -> dict:
        return self._finalize(state, "READY_WITH_CONDITIONS")

    def _finalize(self, state: dict, status: str) -> dict:
        reference = self.artifacts.write_markdown(
            state["workflow_id"],
            "FINAL_ENGINEERING_SUMMARY",
            "13-final-engineering-summary.md",
            state["release_package"],
        )
        self.audit.record(
            state["workflow_id"],
            "WORKFLOW_COMPLETED",
            "COMPLETE",
            {"status": status, "artifact": reference},
        )
        return {
            "workflow_status": status,
            "final_release_status": status,
            "current_stage": "COMPLETE",
            "completed_at": utc_now().isoformat(),
            "artifact_references": {
                **state.get("artifact_references", {}),
                "final_summary": reference,
            },
        }

    def _approval_gate(self, state: dict, gate: ApprovalGate) -> dict:
        pending = state["pending_approval"]
        payload = interrupt({"type": "APPROVAL", "payload": pending})
        normalized = validate_approval_payload(
            payload,
            workflow_id=state["workflow_id"],
            approval_id=pending["approvalId"],
            gate_type=gate,
            state_version=pending["stateVersion"],
            allowed_actions=pending["allowedActions"],
        )
        decision_payload = {
            "action": normalized["action"],
            "comments": normalized["comments"],
            "conditions": normalized["conditions"],
            "decidedBy": normalized["decided_by"],
        }
        self.approvals.decide(state["workflow_id"], pending["approvalId"], decision_payload)
        history = [*state.get("approval_history", []), {"gate_type": gate.value, **normalized}]
        approved_actions = {"APPROVE", "APPROVE_WITH_CONDITIONS"}
        approved = (
            state.get("requirement_analysis", {})
            if gate == ApprovalGate.REQUIREMENT and normalized["action"] in approved_actions
            else state.get("approved_requirement", {})
        )
        references = state.get("artifact_references", {})
        if gate == ApprovalGate.REQUIREMENT and normalized["action"] in approved_actions:
            approved_ref = self.artifacts.write_markdown(
                state["workflow_id"],
                "APPROVED_REQUIREMENTS",
                "03-approved-requirements.md",
                approved,
            )
            references = {**references, "approved_requirements": approved_ref}
        return {
            "last_approval_action": normalized["action"],
            "approval_history": history,
            "pending_approval": {},
            "approved_requirement": approved,
            "workflow_status": "RUNNING",
        }

    def _agent_failure(self, state: dict, retry_key: str, stage: str, exc: Exception) -> dict:
        current_count = state.get("retry_counts", {}).get(retry_key, 0)
        error_code = getattr(exc, "error_code", "AGENT_FAILED")
        category = (
            "STRUCTURED_OUTPUT_ERROR" if error_code == "MODEL_OUTPUT_INVALID" else "UNKNOWN_FAILURE"
        )
        decision = self.retry_policy.decide(retry_key, current_count, category)
        retry_count = decision.next_count if decision.allowed else current_count
        status = "RETRYING" if decision.allowed else "FAILED"
        diagnostics = dict(getattr(exc, "details", {}) or {})
        last_error = {
            "code": error_code,
            "category": category,
            "message": "The agent failed safely.",
            "agent_stage": stage,
            "retry_allowed": decision.allowed,
            "diagnostics": diagnostics,
        }
        retry_counts = {**state.get("retry_counts", {}), retry_key: retry_count}
        with self.sessions.begin() as session:
            WorkflowRepository(session).update_state(
                state["workflow_id"],
                {
                    "workflow_status": status,
                    "current_stage": stage,
                    "state_version": state.get("state_version", 1),
                },
            )
            AuditRepository(session).add(
                state["workflow_id"],
                "RETRY_STARTED" if decision.allowed else "AGENT_RETRY_EXHAUSTED",
                stage,
                {
                    "agent_stage": stage,
                    "retry_count": retry_count,
                    "error_code": error_code,
                },
            )
        return {
            "workflow_status": status,
            "current_stage": stage,
            "retry_counts": retry_counts,
            "last_error": last_error,
            "failure_history": [
                *state.get("failure_history", []),
                {"stage": stage, "error_code": error_code, "retry_count": retry_count},
            ],
        }

    @staticmethod
    def _policy_error(
        code: str, message: str, details: dict[str, object] | None = None
    ) -> dict[str, Any]:
        error: dict[str, object] = {
            "code": code,
            "category": "POLICY_VIOLATION",
            "message": message,
        }
        if details:
            error["details"] = details
        return {"last_error": error}

    @staticmethod
    def _state_error(
        code: str,
        category: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        error: dict[str, object] = {"code": code, "category": category, "message": message}
        if details:
            error["details"] = details
        return {"last_error": error}
