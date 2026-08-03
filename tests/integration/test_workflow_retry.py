import hashlib
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agents.scripted_provider import ScriptedProvider
from app.core.exceptions import ApplicationError
from app.database.models import AgentExecution, ApprovalDecision
from app.main import create_app
from app.orchestration.nodes import WorkflowNodes
from app.tools.models import CommandResult, ToolStatus
from app.tools.test_runner import TestRunner
from tests.phase3_helpers import advance_to_release, approve_pending, create_workflow


def _install_high_risk_coding_retry(
    monkeypatch: pytest.MonkeyPatch, *, validation_failures: int
) -> None:
    original_generate = ScriptedProvider.generate
    validation_calls = 0

    def high_risk_retry(self: ScriptedProvider, **kwargs):
        generated = original_generate(self, **kwargs)
        output = generated.model_dump(mode="json")
        payload = kwargs["input_payload"]
        if kwargs["agent_name"] != "CODING_AGENT":
            return output
        active_task = payload.get("active_task", {})
        if active_task.get("task_id") != "TASK-001":
            return output
        retry_number = int(payload.get("retry_number", 0))
        if retry_number == 0:
            edits = []
        elif retry_number == 1:
            edits = [
                {
                    "operation": "CREATE",
                    "relative_path": "pyproject.toml",
                    "content": "[project]\nname = 'approval-retry'\nversion = '0.1.0'\n",
                    "expected_absent": True,
                    "expected_hash": None,
                    "old_text": None,
                    "replacement_text": None,
                }
            ]
        else:
            edits = [
                {
                    "operation": "MODIFY",
                    "relative_path": "pyproject.toml",
                    "content": (
                        "[project]\nname = 'approval-retry'\nversion = '0.1.1'\n"
                    ),
                    "expected_absent": False,
                    "expected_hash": payload.get("file_hashes", {}).get(
                        "pyproject.toml"
                    ),
                    "old_text": None,
                    "replacement_text": None,
                }
            ]
        output.update(
            change_plan=[
                {
                    "task_id": active_task["task_id"],
                    "paths": [edit["relative_path"] for edit in edits],
                }
            ],
            structured_edits=edits,
            high_risk_change=True,
            high_risk_reason="Project configuration requires human review.",
        )
        return output

    def deterministic_task_validation(
        self: TestRunner, repository_path, command_ids, *, import_modules=None
    ) -> list[CommandResult]:
        del self, repository_path, import_modules
        nonlocal validation_calls
        validation_calls += 1
        failed = validation_calls <= validation_failures
        command_id = command_ids[0] if command_ids else "RUFF_CHECK"
        return [
            CommandResult(
                command_id=command_id,
                status=ToolStatus.FAILED if failed else ToolStatus.SUCCESS,
                exit_code=1 if failed else 0,
                stdout="",
                stderr="current attempt failed" if failed else "",
                duration_ms=1,
            )
        ]

    monkeypatch.setattr(ScriptedProvider, "generate", high_risk_retry)
    monkeypatch.setattr(TestRunner, "run_task_commands", deterministic_task_validation)


def _advance_to_first_high_risk_approval(client: TestClient, workspace: str) -> dict:
    workflow = create_workflow(client, workspace=workspace)
    workflow = approve_pending(client, workflow)
    workflow = approve_pending(client, workflow)
    assert workflow["currentStage"] == "HIGH_RISK_CHANGE_APPROVAL"
    assert workflow["pendingApproval"]["gateType"] == "HIGH_RISK_CHANGE"
    return workflow


def test_high_risk_retry_approval_applies_current_plan_before_validation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_high_risk_coding_retry(monkeypatch, validation_failures=1)
    workflow = _advance_to_first_high_risk_approval(
        client, "high-risk-retry-current-plan"
    )

    retry_approval = approve_pending(client, workflow)
    assert retry_approval["retryCounts"]["coding"] == 1
    assert retry_approval["pendingApproval"]["gateType"] == "HIGH_RISK_CHANGE"

    completed = approve_pending(client, retry_approval)
    audit = client.get(
        f"/api/v1/workflows/{completed['workflowId']}/audit"
    ).json()
    task_events = [
        item
        for item in audit
        if (item["details"] or {}).get("task_id") == "TASK-001"
        or (item["details"] or {}).get("originating_task_id") == "TASK-001"
    ]
    event_types = [item["eventType"] for item in task_events]

    retry_index = event_types.index("RETRY_STARTED")
    applied_index = event_types.index("CHANGES_APPLIED", retry_index + 1)
    validation_index = event_types.index("TASK_VALIDATION_STARTED", applied_index + 1)
    completed_index = event_types.index("TASK_COMPLETED", validation_index + 1)
    assert retry_index < applied_index < validation_index < completed_index
    assert completed["retryCounts"]["coding"] == 1
    assert event_types.count("RETRY_STARTED") == 1
    current_validation = next(
        item
        for item in reversed(task_events)
        if item["eventType"] == "TASK_VALIDATION_COMPLETED"
    )
    assert current_validation["details"]["status"] == "VALIDATION_PASSED"
    assert current_validation["details"]["attempt_number"] == 2
    assert current_validation["details"]["originating_task_id"] == "TASK-001"
    assert current_validation["details"]["retry_task_id"] == "TASK-001-RETRY-1"


def test_current_retry_validation_failure_starts_next_bounded_retry(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_high_risk_coding_retry(monkeypatch, validation_failures=2)
    workflow = _advance_to_first_high_risk_approval(
        client, "high-risk-retry-current-failure"
    )
    retry_approval = approve_pending(client, workflow)

    next_retry_approval = approve_pending(client, retry_approval)
    audit = client.get(
        f"/api/v1/workflows/{next_retry_approval['workflowId']}/audit"
    ).json()
    retries = [
        item
        for item in audit
        if item["eventType"] == "RETRY_STARTED"
        and item["details"].get("originating_task_id") == "TASK-001"
    ]

    assert next_retry_approval["retryCounts"]["coding"] == 2
    assert next_retry_approval["pendingApproval"]["gateType"] == "HIGH_RISK_CHANGE"
    assert len(retries) == 2
    assert retries[-1]["details"]["retry_task_id"] == "TASK-001-RETRY-2"
    assert retries[-1]["details"]["attempt_number"] == 3


def test_coding_retry_then_pass(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = ScriptedProvider.generate
    retry_payloads: list[dict] = []

    def capture_retry(self: ScriptedProvider, **kwargs):
        payload = kwargs["input_payload"]
        if kwargs["agent_name"] == "CODING_AGENT" and payload.get("originating_task"):
            retry_payloads.append(payload)
        return original(self, **kwargs)

    monkeypatch.setattr(ScriptedProvider, "generate", capture_retry)
    workflow = advance_to_release(client, "CODING_RETRY_THEN_PASS", "retry-target")
    assert workflow["retryCounts"]["coding"] == 1
    events = [
        item["eventType"]
        for item in client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
    ]
    assert "RETRY_STARTED" in events
    assert events.count("TASK_VALIDATION_COMPLETED") == 6
    assert events.count("VALIDATION_COMPLETED") == 1
    assert len(retry_payloads) == 1
    payload = retry_payloads[0]
    assert payload["originating_task"]["task_id"] == "TASK-002"
    current_main = next(
        item
        for item in payload["repository_context"]
        if item["relative_path"] == "sample_app/main.py"
    )
    assert 'return "wrong"' in current_main["content"]
    assert current_main["sha256"] == hashlib.sha256(
        current_main["content"].encode("utf-8")
    ).hexdigest()

    audit = client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
    retry = next(item for item in audit if item["eventType"] == "RETRY_STARTED")
    assert retry["details"]["originating_task_id"] == "TASK-002"
    assert retry["details"]["retry_task_id"] == "TASK-002-RETRY-1"
    assert retry["details"]["validation_command"] == "PYTEST"
    assert retry["details"]["failure_category"] == "IMPLEMENTATION_DEFECT"
    assert retry["details"]["attempt_number"] == 2


def _model_failure() -> ApplicationError:
    return ApplicationError(
        "The model provider could not produce valid structured output.",
        "MODEL_OUTPUT_INVALID",
        502,
        details={
            "agent_name": "DESIGN_AGENT",
            "exception_class": "ValidationError",
            "field_paths": ["components.0.name"],
            "validation_error_types": ["missing"],
            "finish_reason": "stop",
            "input_tokens": 100,
            "output_tokens": 20,
            "http_request_made": True,
        },
    )


def _design_executions(app: FastAPI, workflow_id: str) -> list[AgentExecution]:
    with app.state.workflow_runtime.sessions() as session:
        return list(
            session.scalars(
                select(AgentExecution)
                .where(
                    AgentExecution.workflow_id == workflow_id,
                    AgentExecution.agent_name == "DESIGN_AGENT",
                )
                .order_by(AgentExecution.started_at)
            )
        )


def _approval_decision_count(app: FastAPI, workflow_id: str) -> int:
    with app.state.workflow_runtime.sessions() as session:
        return len(
            list(
                session.scalars(
                    select(ApprovalDecision).where(ApprovalDecision.workflow_id == workflow_id)
                )
            )
        )


def test_design_failure_retries_once_then_continues_without_reapproval(
    app: FastAPI,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = ScriptedProvider.generate
    design_calls = 0

    def flaky(self: ScriptedProvider, **kwargs):
        nonlocal design_calls
        if kwargs["agent_name"] == "DESIGN_AGENT":
            design_calls += 1
            if design_calls == 1:
                raise _model_failure()
        return original(self, **kwargs)

    monkeypatch.setattr(ScriptedProvider, "generate", flaky)
    workflow = create_workflow(client, workspace="design-retry-success")
    resumed = approve_pending(client, workflow)
    assert resumed["status"] == "WAITING_FOR_ARCHITECTURE_APPROVAL"
    assert resumed["currentStage"] == "ARCHITECTURE_APPROVAL"
    assert resumed["retryCounts"]["design"] == 1
    assert resumed["planVersion"] == 1
    assert _approval_decision_count(app, workflow["workflowId"]) == 1
    executions = _design_executions(app, workflow["workflowId"])
    assert [(item.attempt_number, item.status) for item in executions] == [
        (1, "FAILED"),
        (2, "COMPLETED"),
    ]
    diagnostics = executions[0].error_message or ""
    assert '"exception_class": "ValidationError"' in diagnostics
    assert "components.0.name" in diagnostics


def test_design_retry_exhaustion_never_leaves_workflow_running(
    app: FastAPI,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = ScriptedProvider.generate

    def failing(self: ScriptedProvider, **kwargs):
        if kwargs["agent_name"] == "DESIGN_AGENT":
            raise _model_failure()
        return original(self, **kwargs)

    monkeypatch.setattr(ScriptedProvider, "generate", failing)
    workflow = create_workflow(client, workspace="design-retry-exhausted")
    result = approve_pending(client, workflow)
    assert result["status"] == "SAFE_STOPPED"
    assert result["status"] != "RUNNING"
    assert result["retryCounts"]["design"] == 1
    assert _approval_decision_count(app, workflow["workflowId"]) == 1
    executions = _design_executions(app, workflow["workflowId"])
    assert [(item.attempt_number, item.status) for item in executions] == [
        (1, "FAILED"),
        (2, "FAILED"),
    ]


class SimulatedProcessExit(BaseException):
    pass


def test_restart_preserves_design_retryable_checkpoint(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original: Callable = ScriptedProvider.generate
    design_calls = 0

    def interrupted(self: ScriptedProvider, **kwargs):
        nonlocal design_calls
        if kwargs["agent_name"] == "DESIGN_AGENT":
            design_calls += 1
            if design_calls == 1:
                raise _model_failure()
            if design_calls == 2:
                raise SimulatedProcessExit()
        return original(self, **kwargs)

    monkeypatch.setattr(ScriptedProvider, "generate", interrupted)
    with TestClient(app) as first:
        workflow = create_workflow(first, workspace="design-retry-restart")
        pending = workflow["pendingApproval"]
        with pytest.raises(SimulatedProcessExit):
            app.state.workflow_service.approve(
                workflow["workflowId"],
                pending["approvalId"],
                {
                    "gateType": pending["gateType"],
                    "stateVersion": pending["stateVersion"],
                    "action": "APPROVE",
                    "comments": "Approve once",
                    "conditions": [],
                    "decidedBy": "test-user",
                },
            )
        retrying = app.state.workflow_service.get(workflow["workflowId"])
        assert retrying["status"] == "RETRYING"
        assert retrying["currentStage"] == "DESIGN"
        assert retrying["retryCounts"]["design"] == 1
        settings = app.state.workflow_runtime.settings

    restarted_app = create_app(settings)
    with TestClient(restarted_app) as restarted:
        response = restarted.post(f"/api/v1/workflows/{workflow['workflowId']}/retry")
        assert response.status_code == 200, response.text
        resumed = response.json()
        assert resumed["status"] == "WAITING_FOR_ARCHITECTURE_APPROVAL"
        assert resumed["retryCounts"]["design"] == 1
        assert _approval_decision_count(restarted_app, workflow["workflowId"]) == 1
        events = restarted.get(
            f"/api/v1/workflows/{workflow['workflowId']}/audit"
        ).json()
        assert sum(item["eventType"] == "RETRY_STARTED" for item in events) == 1


def test_legacy_design_failure_checkpoint_can_be_retried_without_reapproval(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guarded_design_node = WorkflowNodes.design_agent
    original_provider = ScriptedProvider.generate
    design_calls = 0

    def legacy_design_node(self: WorkflowNodes, state: dict) -> dict:
        output = self.design.run(state)
        return {"architecture_design": output, "current_stage": "DESIGN"}

    def fail_once(self: ScriptedProvider, **kwargs):
        nonlocal design_calls
        if kwargs["agent_name"] == "DESIGN_AGENT":
            design_calls += 1
            if design_calls == 1:
                raise _model_failure()
        return original_provider(self, **kwargs)

    monkeypatch.setattr(WorkflowNodes, "design_agent", legacy_design_node)
    monkeypatch.setattr(ScriptedProvider, "generate", fail_once)
    with TestClient(app) as first:
        workflow = create_workflow(first, workspace="legacy-design-retry")
        pending = workflow["pendingApproval"]
        failed = first.post(
            f"/api/v1/workflows/{workflow['workflowId']}/approvals/{pending['approvalId']}",
            json={
                "gateType": pending["gateType"],
                "stateVersion": pending["stateVersion"],
                "action": "APPROVE",
                "comments": "Approve once",
                "conditions": [],
                "decidedBy": "test-user",
            },
        )
        assert failed.status_code == 502
        assert failed.json()["errorCode"] == "MODEL_OUTPUT_INVALID"
        stuck = first.get(f"/api/v1/workflows/{workflow['workflowId']}").json()
        assert stuck["status"] == "RUNNING"
        assert stuck["currentStage"] == "REQUIREMENT_APPROVAL"
        settings = app.state.workflow_runtime.settings

    monkeypatch.setattr(WorkflowNodes, "design_agent", guarded_design_node)
    restarted_app = create_app(settings)
    with TestClient(restarted_app) as restarted:
        response = restarted.post(f"/api/v1/workflows/{workflow['workflowId']}/retry")
        assert response.status_code == 200, response.text
        resumed = response.json()
        assert resumed["status"] == "WAITING_FOR_ARCHITECTURE_APPROVAL"
        assert resumed["retryCounts"]["design"] == 1
        assert _approval_decision_count(restarted_app, workflow["workflowId"]) == 1
        executions = _design_executions(restarted_app, workflow["workflowId"])
        assert [(item.attempt_number, item.status) for item in executions] == [
            (1, "FAILED"),
            (2, "COMPLETED"),
        ]
        events = restarted.get(
            f"/api/v1/workflows/{workflow['workflowId']}/audit"
        ).json()
        retry_started = [item for item in events if item["eventType"] == "RETRY_STARTED"]
        recovered = [
            item for item in events if item["eventType"] == "AGENT_RETRY_RECOVERED"
        ]
        assert len(retry_started) == 1
        assert retry_started[0]["details"] == {
            "agent": "DESIGN_AGENT",
            "retry_count": 1,
            "source": "LEGACY_FAILED_CHECKPOINT",
        }
        assert len(recovered) == 1
        event_types = [item["eventType"] for item in events]
        failed_index = event_types.index("AGENT_FAILED")
        retry_index = event_types.index("RETRY_STARTED")
        recovered_index = event_types.index("AGENT_RETRY_RECOVERED")
        second_started_index = [
            index
            for index, item in enumerate(events)
            if item["eventType"] == "AGENT_STARTED" and item["stage"] == "DESIGN"
        ][1]
        assert failed_index < retry_index < recovered_index < second_started_index

        duplicate = restarted.post(f"/api/v1/workflows/{workflow['workflowId']}/retry")
        assert duplicate.status_code == 409
        after_duplicate = restarted.get(
            f"/api/v1/workflows/{workflow['workflowId']}/audit"
        ).json()
        assert sum(item["eventType"] == "RETRY_STARTED" for item in after_duplicate) == 1
        assert (
            sum(item["eventType"] == "AGENT_RETRY_RECOVERED" for item in after_duplicate)
            == 1
        )
        current = restarted.get(f"/api/v1/workflows/{workflow['workflowId']}").json()
        assert current["retryCounts"]["design"] == 1
        assert _approval_decision_count(restarted_app, workflow["workflowId"]) == 1
