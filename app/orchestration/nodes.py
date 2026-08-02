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
from app.orchestration.replanning import mark_for_replanning
from app.orchestration.retries import RetryPolicy
from app.orchestration.rollback import perform_rollback
from app.orchestration.safe_stop import safe_stop_workflow
from app.repositories.workflow_repository import WorkflowRepository
from app.schemas.agents.common import ApprovalGate
from app.services.approval_service import ApprovalService
from app.services.artifact_service import ArtifactService
from app.services.audit_service import AuditService
from app.tools.controlled_editor import ControlledEditor, file_sha256
from app.tools.git_tool import GitTool
from app.tools.models import StructuredEdit, ToolStatus
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
        version = state.get("state_version", 1) + 1
        pending = {
            "type": "CLARIFICATION",
            "payload": {"questions": questions, "stateVersion": version},
        }
        self.audit.record(
            state["workflow_id"],
            "CLARIFICATION_REQUESTED",
            "CLARIFICATION",
            {"question_count": len(questions)},
        )
        return {
            "pending_interaction": pending,
            "state_version": version,
            "workflow_status": "WAITING_FOR_CLARIFICATION",
            "current_stage": "CLARIFICATION",
        }

    def clarification_gate(self, state: dict) -> dict:
        questions = state["requirement_analysis"].get("clarification_questions", [])
        version = state["state_version"]
        payload = interrupt(state["pending_interaction"])
        answers = validate_clarification_payload(
            payload,
            workflow_id=state["workflow_id"],
            state_version=version,
            question_ids=[question["question_id"] for question in questions],
        )
        self.audit.record(
            state["workflow_id"],
            "CLARIFICATION_SUBMITTED",
            "CLARIFICATION",
            {"answer_count": len(answers)},
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
            "state_version": version,
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
        output = self.design.run(state)
        version = state.get("architecture_version", 0) + 1
        self.audit.record(
            state["workflow_id"], "DESIGN_VERSION_CREATED", "DESIGN", {"version": version}
        )
        return {
            "architecture_design": output,
            "architecture_version": version,
            "workflow_status": "DESIGNING",
            "current_stage": "DESIGN",
        }

    def design_validation(self, state: dict) -> dict:
        if state.get("architecture_design", {}).get("status") != "DESIGN_COMPLETE":
            return self._policy_error("INCONSISTENT_STATE", "The design is not complete.")
        return {}

    def planning_agent(self, state: dict) -> dict:
        output = self.planning.run(state)
        version = state.get("plan_version", 0) + 1
        with self.sessions.begin() as session:
            WorkflowRepository(session).replace_tasks(state["workflow_id"], output)
        self.audit.record(
            state["workflow_id"], "PLAN_VERSION_CREATED", "PLANNING", {"version": version}
        )
        return {
            "implementation_plan": output,
            "plan_version": version,
            "workflow_status": "PLANNING",
            "current_stage": "PLANNING",
        }

    def plan_validation(self, state: dict) -> dict:
        plan = state.get("implementation_plan", {})
        if plan.get("status") != "PLAN_COMPLETE" or not plan.get("tasks"):
            return self._policy_error("INCONSISTENT_STATE", "The plan is not executable.")
        return {}

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
        return self._approval_gate(state, ApprovalGate.ARCHITECTURE_AND_PLAN)

    def workspace_setup(self, state: dict) -> dict:
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

    def repository_analysis(self, state: dict) -> dict:
        repository = Path(state["repository_path"])
        scan = self.scanner.scan(repository).model_dump(mode="json")
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
        hashes = {}
        for name in state.get("changed_files", []):
            candidate = repository / name
            if candidate.is_file():
                hashes[name] = file_sha256(candidate)
        output = self.repository_coding.code(state, hashes)
        self.audit.record(
            state["workflow_id"],
            "CHANGE_PLAN_CREATED",
            "CODING",
            {"edit_count": len(output["structured_edits"])},
        )
        return {
            "code_change_plan": output,
            "workflow_status": "IMPLEMENTING",
            "current_stage": "CODING",
            "last_error": {},
        }

    def change_policy_validation(self, state: dict) -> dict:
        allowed = [
            path
            for task in state["implementation_plan"].get("tasks", [])
            for path in task.get("allowed_paths", [])
        ]
        for item in state["code_change_plan"]["structured_edits"]:
            edit = StructuredEdit.model_validate(item)
            if not any(
                edit.relative_path == path or edit.relative_path.startswith(f"{path}/")
                for path in allowed
            ):
                return self._policy_error(
                    "REPOSITORY_POLICY_VIOLATION", "An edit path was not approved."
                )
        return {}

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
        allowed = [
            path
            for task in state["implementation_plan"].get("tasks", [])
            for path in task.get("allowed_paths", [])
        ]
        for edit in edits:
            if not any(
                edit.relative_path == path or edit.relative_path.startswith(f"{path}/")
                for path in allowed
            ):
                return self._policy_error(
                    "REPOSITORY_POLICY_VIOLATION", "An edit path was not approved."
                )
        repository = Path(state["repository_path"])
        result = self.editor.apply_batch(repository, edits)
        if result.status != ToolStatus.SUCCESS:
            code = result.error.code if result.error else "EDIT_FAILED"
            return self._policy_error(code, "A controlled edit was blocked.")
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
            state["workflow_id"], "CHANGES_APPLIED", "CODING", {"changed_files": changed}
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

    def parallel_start(self, state: dict) -> dict:
        return {
            "workflow_status": "VALIDATING",
            "current_stage": "PARALLEL_VALIDATION_DOCUMENTATION",
        }

    def validation_agent(self, state: dict) -> dict:
        self.audit.record(state["workflow_id"], "VALIDATION_STARTED", "VALIDATION")
        suite = self.tests.run_validation_suite(Path(state["repository_path"]))
        results = [suite.ruff.model_dump(mode="json")]
        if suite.pytest is not None:
            results.append(suite.pytest.model_dump(mode="json"))
        output = self.validation.run(state, results)
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
            "validation_branch_complete": True,
            "artifact_references": {
                **state.get("artifact_references", {}),
                "quality_review": quality_ref,
            },
        }

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
        category = state.get("validation_result", {}).get("failure_category")
        return {"last_error": {"category": category}} if category else {}

    def retry_router(self, state: dict) -> dict:
        current = state.get("retry_counts", {}).get("coding", 0)
        category = state.get("validation_result", {}).get("failure_category")
        decision = self.retry_policy.decide("coding", current, category)
        counts = {**state.get("retry_counts", {}), "coding": decision.next_count}
        if decision.allowed:
            self.audit.record(
                state["workflow_id"], "RETRY_STARTED", "CODING", {"retry": decision.next_count}
            )
        return {
            "retry_counts": counts,
            "last_error": {"category": category, "retry_allowed": decision.allowed},
            "workflow_status": "RETRYING",
            "current_stage": "RETRY",
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

    @staticmethod
    def _policy_error(code: str, message: str) -> dict[str, Any]:
        return {"last_error": {"code": code, "category": "POLICY_VIOLATION", "message": message}}
