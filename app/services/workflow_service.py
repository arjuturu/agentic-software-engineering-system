from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langgraph.types import Command
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.agents.base import PromptLoader
from app.agents.design_agent import DesignAgent
from app.agents.documentation_release_agent import DocumentationReleaseAgent
from app.agents.planning_agent import PlanningAgent
from app.agents.provider import create_provider
from app.agents.repository_coding_agent import RepositoryCodingAgent
from app.agents.requirement_agent import RequirementAgent
from app.agents.runner import AgentRunner
from app.agents.validation_agent import ValidationAgent
from app.artifacts.writer import ArtifactWriter
from app.config import Settings
from app.core.exceptions import ApplicationError
from app.core.identifiers import new_correlation_id, new_thread_id, new_workflow_id
from app.core.time import utc_now
from app.database.models import AgentExecution, ApprovalDecision, WorkflowRun
from app.orchestration.approvals import validate_clarification_payload
from app.orchestration.checkpoint import CheckpointManager
from app.orchestration.graph import build_workflow_graph
from app.orchestration.nodes import WorkflowNodes
from app.orchestration.retries import RetryPolicy
from app.repositories.audit_repository import AuditRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.scenarios.resolver import resolve_scenario_profile
from app.scenarios.url_shortener.validators import URLShortenerValidator
from app.schemas.workflows import WorkflowCreateRequest
from app.services.approval_service import ApprovalService
from app.services.artifact_service import ArtifactService
from app.services.audit_service import AuditService
from app.tools.alembic_runner import AlembicRunner
from app.tools.command_runner import CommandRunner
from app.tools.controlled_editor import ControlledEditor
from app.tools.git_tool import GitTool
from app.tools.path_policy import PathPolicy, PathPolicyError
from app.tools.repository_scanner import RepositoryScanner
from app.tools.test_runner import TestRunner
from app.tools.workspace_manager import WorkspaceManager


@dataclass
class WorkflowRuntime:
    settings: Settings
    sessions: sessionmaker[Session]
    checkpoint: CheckpointManager
    graph: Any
    artifacts: ArtifactService
    audit: AuditService
    approvals: ApprovalService
    workspace: WorkspaceManager

    def close(self) -> None:
        self.checkpoint.close()


def create_workflow_runtime(settings: Settings, sessions: sessionmaker[Session]) -> WorkflowRuntime:
    settings.WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    settings.ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    policy = PathPolicy(settings)
    artifact_service = ArtifactService(sessions, ArtifactWriter(policy))
    audit_service = AuditService(sessions)
    approval_service = ApprovalService(sessions)
    runner = AgentRunner(
        create_provider(settings),
        PromptLoader(Path(__file__).resolve().parents[2] / "prompts"),
        sessions,
        artifact_service,
    )
    command_runner = CommandRunner(policy, settings)
    test_runner = TestRunner(command_runner)
    git_tool = GitTool(policy, settings)
    target_validator = URLShortenerValidator(
        policy,
        RepositoryScanner(policy, settings),
        command_runner,
        test_runner,
        AlembicRunner(command_runner),
        git_tool,
    )
    workspace_manager = WorkspaceManager(policy)
    nodes = WorkflowNodes(
        sessions=sessions,
        requirement=RequirementAgent(runner),
        design=DesignAgent(runner),
        planning=PlanningAgent(runner),
        repository_coding=RepositoryCodingAgent(runner),
        validation=ValidationAgent(runner),
        documentation=DocumentationReleaseAgent(runner),
        approvals=approval_service,
        artifacts=artifact_service,
        audit=audit_service,
        retry_policy=RetryPolicy(settings),
        workspace=workspace_manager,
        scanner=RepositoryScanner(policy, settings),
        editor=ControlledEditor(policy, settings),
        git=git_tool,
        tests=test_runner,
        target_validator=target_validator,
    )
    checkpoint = CheckpointManager(settings)
    return WorkflowRuntime(
        settings=settings,
        sessions=sessions,
        checkpoint=checkpoint,
        graph=build_workflow_graph(nodes, checkpoint.checkpointer),
        artifacts=artifact_service,
        audit=audit_service,
        approvals=approval_service,
        workspace=workspace_manager,
    )


class WorkflowService:
    def __init__(self, runtime: WorkflowRuntime) -> None:
        self.runtime = runtime

    def create(self, request: WorkflowCreateRequest, correlation_id: str | None = None) -> dict:
        if (
            self.runtime.settings.LLM_MODE == "OPENAI"
            and request.scripted_scenario.value != "HAPPY_PATH"
        ):
            raise ApplicationError(
                "Scripted scenarios are unavailable in OpenAI mode.",
                "INVALID_SCRIPTED_SCENARIO",
                400,
            )
        if request.scenario_type.value == "BROWNFIELD":
            try:
                self.runtime.workspace.validate_brownfield_source(
                    request.source_workspace or "", request.workspace_name
                )
            except PathPolicyError as exc:
                status_code = 404 if exc.error_code == "SOURCE_WORKSPACE_NOT_FOUND" else 409
                if exc.error_code in {
                    "INVALID_WORKSPACE_NAME",
                    "ABSOLUTE_PATH",
                    "PATH_TRAVERSAL",
                    "SOURCE_SYMLINK_BLOCKED",
                }:
                    status_code = 400
                raise ApplicationError(
                    "The Brownfield workspace request is invalid.",
                    exc.error_code,
                    status_code,
                ) from exc
        workflow_id = new_workflow_id()
        thread_id = new_thread_id()
        active_correlation_id = correlation_id or new_correlation_id()
        scenario_profile = resolve_scenario_profile(
            request.scenario_type.value, request.requirement
        )
        now = utc_now().isoformat()
        with self.runtime.sessions.begin() as session:
            WorkflowRepository(session).add(
                WorkflowRun(
                    id=workflow_id,
                    thread_id=thread_id,
                    correlation_id=active_correlation_id,
                    scenario_type=request.scenario_type.value,
                    repository_path=request.workspace_name,
                    status="CREATED",
                    current_stage="CREATED",
                    state_version=1,
                )
            )
            AuditRepository(session).add(
                workflow_id,
                "WORKFLOW_CREATED",
                "CREATED",
                {
                    "scenario_type": request.scenario_type.value,
                    "scenario_profile": scenario_profile["profile_id"],
                },
            )
        state = {
            "workflow_id": workflow_id,
            "thread_id": thread_id,
            "correlation_id": active_correlation_id,
            "scenario_type": request.scenario_type.value,
            "scenario_profile": scenario_profile,
            "execution_mode": self.runtime.settings.LLM_MODE,
            "scripted_scenario": request.scripted_scenario.value,
            "workspace_name": request.workspace_name,
            "source_workspace": request.source_workspace or "",
            "repository_path": "",
            "original_requirement": request.requirement,
            "clarification_answers": [],
            "requirement_version": 1,
            "architecture_version": 0,
            "plan_version": 0,
            "pending_interaction": {},
            "pending_approval": {},
            "approval_history": [],
            "retry_counts": {},
            "failure_history": [],
            "replanning_history": [],
            "rollback_history": [],
            "artifact_references": {},
            "state_version": 1,
            "workflow_status": "CREATED",
            "current_stage": "CREATED",
            "final_release_status": "",
            "started_at": now,
            "updated_at": now,
        }
        self.runtime.graph.invoke(state, self._config(thread_id))
        return self._snapshot(workflow_id, thread_id)

    def get(self, workflow_id: str) -> dict:
        with self.runtime.sessions() as session:
            item = WorkflowRepository(session).get(workflow_id)
            return self._snapshot(item.id, item.thread_id)

    def clarify(self, workflow_id: str, payload: dict) -> dict:
        item = self._row(workflow_id)
        request_workflow_id = payload.get("workflowId")
        clarification_id = payload.get("clarificationId")
        if request_workflow_id != workflow_id or not isinstance(clarification_id, str):
            raise ApplicationError(
                "The clarification was not found.", "CLARIFICATION_NOT_FOUND", 404
            )
        with self.runtime.sessions() as session:
            stored = WorkflowRepository(session).clarification(workflow_id, clarification_id)
        if stored is None:
            raise ApplicationError(
                "The clarification was not found.", "CLARIFICATION_NOT_FOUND", 404
            )
        if item.status != "WAITING_FOR_CLARIFICATION":
            if stored.get("status") == "COMPLETED":
                raise ApplicationError(
                    "Clarification was already submitted.",
                    "CLARIFICATION_ALREADY_SUBMITTED",
                    409,
                )
            raise ApplicationError(
                "The workflow is not waiting for clarification.", "WORKFLOW_NOT_WAITING", 409
            )
        graph_state = dict(self.runtime.graph.get_state(self._config(item.thread_id)).values)
        pending = graph_state.get("pending_interaction", {})
        pending_payload = pending.get("payload", {})
        expected_version = pending_payload.get("stateVersion")
        graph_version = graph_state.get("state_version")
        if (
            graph_state.get("workflow_id") != workflow_id
            or pending.get("type") != "CLARIFICATION"
            or pending_payload.get("clarificationId") != clarification_id
        ):
            raise ApplicationError(
                "The clarification was not found.", "CLARIFICATION_NOT_FOUND", 404
            )
        if (
            not isinstance(expected_version, int)
            or item.state_version != expected_version
            or graph_version != expected_version
            or stored.get("stateVersion") != expected_version
        ):
            raise ApplicationError(
                "Clarification state does not match.", "INVALID_STATE_VERSION", 409
            )
        resume = {"type": "CLARIFICATION_RESPONSE", **payload}
        validate_clarification_payload(
            resume,
            workflow_id=workflow_id,
            clarification_id=clarification_id,
            state_version=expected_version,
            question_ids=[
                question["question_id"] for question in pending_payload.get("questions", [])
            ],
        )
        self.runtime.graph.invoke(Command(resume=resume), self._config(item.thread_id))
        return self._snapshot(workflow_id, item.thread_id)

    def retry(self, workflow_id: str) -> dict:
        item = self._row(workflow_id)
        config = self._config(item.thread_id)
        snapshot = self.runtime.graph.get_state(config)
        state = dict(snapshot.values)
        retryable = (
            state.get("workflow_status") == "RETRYING"
            and state.get("current_stage") == "DESIGN"
            and state.get("last_error", {}).get("retry_allowed") is True
            and tuple(snapshot.next) == ("design_agent",)
        )
        legacy_recovery = False
        if not retryable:
            if not self._legacy_design_retry_candidate(item, snapshot, state):
                raise ApplicationError(
                    "The workflow has no controlled retry available.",
                    "WORKFLOW_NOT_RETRYABLE",
                    409,
                )
            legacy_recovery = True
            retry_counts = {**state.get("retry_counts", {}), "design": 1}
            last_error = {
                "code": "MODEL_OUTPUT_INVALID",
                "category": "STRUCTURED_OUTPUT_ERROR",
                "message": "The Design Agent failed safely.",
                "agent_stage": "DESIGN",
                "retry_allowed": True,
                "diagnostics": {"legacy_diagnostics_unavailable": True},
            }
            self.runtime.graph.update_state(
                config,
                {
                    "workflow_status": "RETRYING",
                    "current_stage": "DESIGN",
                    "retry_counts": retry_counts,
                    "last_error": last_error,
                    "failure_history": [
                        *state.get("failure_history", []),
                        {
                            "stage": "DESIGN",
                            "error_code": "MODEL_OUTPUT_INVALID",
                            "retry_count": 1,
                        },
                    ],
                },
                as_node="design_agent",
            )
            with self.runtime.sessions.begin() as session:
                WorkflowRepository(session).update_state(
                    workflow_id,
                    {
                        "workflow_status": "RETRYING",
                        "current_stage": "DESIGN",
                        "state_version": state.get("state_version", item.state_version),
                    },
                )
                self._ensure_retry_audits(session, workflow_id, legacy_recovery=True)
        if not legacy_recovery:
            with self.runtime.sessions.begin() as session:
                self._ensure_retry_audits(session, workflow_id, legacy_recovery=False)
        self.runtime.graph.invoke(None, config)
        return self._snapshot(workflow_id, item.thread_id)

    @staticmethod
    def _ensure_retry_audits(
        session: Session, workflow_id: str, *, legacy_recovery: bool
    ) -> None:
        audits = AuditRepository(session)
        if not audits.exists(workflow_id, "RETRY_STARTED", "DESIGN"):
            audits.add(
                workflow_id,
                "RETRY_STARTED",
                "DESIGN",
                {
                    "agent": "DESIGN_AGENT",
                    "retry_count": 1,
                    "source": (
                        "LEGACY_FAILED_CHECKPOINT" if legacy_recovery else "CONTROLLED_RETRY"
                    ),
                },
            )
        if legacy_recovery and not audits.exists(
            workflow_id, "AGENT_RETRY_RECOVERED", "DESIGN"
        ):
            audits.add(
                workflow_id,
                "AGENT_RETRY_RECOVERED",
                "DESIGN",
                {"retry_count": 1, "source": "LEGACY_FAILED_CHECKPOINT"},
            )

    def _legacy_design_retry_candidate(self, item: WorkflowRun, snapshot, state: dict) -> bool:
        if not (
            item.status == "RUNNING"
            and item.current_stage == "REQUIREMENT_APPROVAL"
            and state.get("last_approval_action") in {"APPROVE", "APPROVE_WITH_CONDITIONS"}
            and not state.get("pending_approval")
            and not state.get("retry_counts")
            and not state.get("last_error")
            and tuple(snapshot.next) == ("design_agent",)
            and any(getattr(task, "error", None) for task in snapshot.tasks)
        ):
            return False
        with self.runtime.sessions() as session:
            approval_count = session.scalar(
                select(func.count())
                .select_from(ApprovalDecision)
                .where(
                    ApprovalDecision.workflow_id == item.id,
                    ApprovalDecision.action.in_(("APPROVE", "APPROVE_WITH_CONDITIONS")),
                )
            )
            failed_design_count = session.scalar(
                select(func.count())
                .select_from(AgentExecution)
                .where(
                    AgentExecution.workflow_id == item.id,
                    AgentExecution.agent_name == "DESIGN_AGENT",
                    AgentExecution.status == "FAILED",
                    AgentExecution.attempt_number == 1,
                )
            )
        return approval_count == 1 and failed_design_count == 1

    def approve(self, workflow_id: str, approval_id: str, payload: dict) -> dict:
        item = self._row(workflow_id)
        if not item.status.startswith("WAITING_FOR_"):
            raise ApplicationError(
                "The workflow is not waiting for approval.", "WORKFLOW_NOT_WAITING", 409
            )
        complete = {
            "type": "APPROVAL_DECISION",
            "workflowId": workflow_id,
            "approvalId": approval_id,
            **payload,
        }
        self.runtime.approvals.validate_for_resume(workflow_id, approval_id, complete)
        self.runtime.graph.invoke(Command(resume=complete), self._config(item.thread_id))
        return self._snapshot(workflow_id, item.thread_id)

    def _row(self, workflow_id: str) -> WorkflowRun:
        with self.runtime.sessions() as session:
            item = WorkflowRepository(session).get(workflow_id)
            session.expunge(item)
            return item

    def _snapshot(self, workflow_id: str, thread_id: str) -> dict:
        snapshot = dict(self.runtime.graph.get_state(self._config(thread_id)).values)
        with self.runtime.sessions.begin() as session:
            item = WorkflowRepository(session).update_state(workflow_id, snapshot)
            result = self._response(item, snapshot)
        return result

    @staticmethod
    def _config(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    @staticmethod
    def _response(item: WorkflowRun, state: dict) -> dict:
        return {
            "workflowId": item.id,
            "threadId": item.thread_id,
            "status": state.get("workflow_status", item.status),
            "currentStage": state.get("current_stage", item.current_stage),
            "stateVersion": state.get("state_version", item.state_version),
            "workspacePath": state.get("workspace_name", item.repository_path),
            "scenarioProfile": state.get("scenario_profile", {}),
            "requirementVersion": state.get("requirement_version", 1),
            "architectureVersion": state.get("architecture_version", 0),
            "planVersion": state.get("plan_version", 0),
            "retryCounts": state.get("retry_counts", {}),
            "pendingInteraction": state.get("pending_interaction", {}),
            "pendingApproval": state.get("pending_approval", {}),
            "finalReleaseStatus": state.get("final_release_status", ""),
            "startedAt": item.started_at,
            "updatedAt": item.updated_at,
            "completedAt": item.completed_at,
        }
