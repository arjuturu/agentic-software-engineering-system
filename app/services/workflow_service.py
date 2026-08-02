from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langgraph.types import Command
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
from app.database.models import WorkflowRun
from app.orchestration.checkpoint import CheckpointManager
from app.orchestration.graph import build_workflow_graph
from app.orchestration.nodes import WorkflowNodes
from app.orchestration.retries import RetryPolicy
from app.repositories.audit_repository import AuditRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.schemas.workflows import WorkflowCreateRequest
from app.services.approval_service import ApprovalService
from app.services.artifact_service import ArtifactService
from app.services.audit_service import AuditService
from app.tools.command_runner import CommandRunner
from app.tools.controlled_editor import ControlledEditor
from app.tools.git_tool import GitTool
from app.tools.path_policy import PathPolicy
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
        workspace=WorkspaceManager(policy),
        scanner=RepositoryScanner(policy, settings),
        editor=ControlledEditor(policy, settings),
        git=GitTool(policy, settings),
        tests=TestRunner(command_runner),
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
        workflow_id = new_workflow_id()
        thread_id = new_thread_id()
        now = utc_now().isoformat()
        with self.runtime.sessions.begin() as session:
            WorkflowRepository(session).add(
                WorkflowRun(
                    id=workflow_id,
                    thread_id=thread_id,
                    correlation_id=correlation_id or new_correlation_id(),
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
                {"scenario_type": request.scenario_type.value},
            )
        state = {
            "workflow_id": workflow_id,
            "thread_id": thread_id,
            "correlation_id": correlation_id or new_correlation_id(),
            "scenario_type": request.scenario_type.value,
            "scripted_scenario": request.scripted_scenario.value,
            "workspace_name": request.workspace_name,
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
        if item.status != "WAITING_FOR_CLARIFICATION":
            raise ApplicationError(
                "The workflow is not waiting for clarification.", "WORKFLOW_NOT_WAITING", 409
            )
        resume = {"type": "CLARIFICATION_RESPONSE", "workflowId": workflow_id, **payload}
        self.runtime.graph.invoke(Command(resume=resume), self._config(item.thread_id))
        return self._snapshot(workflow_id, item.thread_id)

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
