import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agents.planning_agent import PlanningAgent
from app.agents.scripted_provider import ScriptedProvider
from app.database.models import AgentExecution, WorkflowTask
from app.main import create_app
from tests.phase3_helpers import approve_pending, create_workflow


def test_empty_scenario_restrictions_produce_executable_plan(
    app: FastAPI, client: TestClient
) -> None:
    workflow = create_workflow(client, workspace="empty-scenario-planning")

    result = approve_pending(client, workflow)

    assert result["status"] == "WAITING_FOR_ARCHITECTURE_APPROVAL"
    checkpoint = app.state.workflow_runtime.graph.get_state(
        {"configurable": {"thread_id": workflow["threadId"]}}
    ).values
    assert checkpoint["scenario_path_policy"]["mode"] == "TASK_SCOPED"
    assert checkpoint["scenario_path_policy"]["scenario_restrictions"] == []
    assert checkpoint["implementation_plan"]["status"] == "PLAN_COMPLETE"
    assert checkpoint["implementation_plan"]["tasks"]


def test_invalid_blocked_plan_safe_stops_as_planning_failure(
    app: FastAPI, client: TestClient, monkeypatch
) -> None:
    original = ScriptedProvider._planning

    def blocked_by_empty_paths(payload, scenario, retry_number):
        plan = original(payload, scenario, retry_number)
        return {
            **plan,
            "plan_summary": "Incorrectly treated empty scenario paths as deny-all.",
            "tasks": [],
            "execution_order": [],
            "critical_path": [],
            "status": "BLOCKED",
        }

    monkeypatch.setattr(ScriptedProvider, "_planning", staticmethod(blocked_by_empty_paths))
    workflow = create_workflow(client, workspace="blocked-planning-classification")

    result = approve_pending(client, workflow)

    assert result["status"] == "SAFE_STOPPED"
    checkpoint = app.state.workflow_runtime.graph.get_state(
        {"configurable": {"thread_id": workflow["threadId"]}}
    ).values
    assert checkpoint["last_error"]["code"] == "PLAN_NOT_EXECUTABLE"
    assert checkpoint["last_error"]["category"] == "PLANNING_FAILURE"
    error_codes = {
        item["code"]
        for item in checkpoint["last_error"]["details"]["validation_errors"]
    }
    assert "EMPTY_SCENARIO_PATHS_NOT_BLOCKING" in error_codes
    audit = client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
    assert sum(item["eventType"] == "PLAN_VALIDATION_FAILED" for item in audit) == 3
    assert sum(item["eventType"] == "PLAN_CORRECTION_STARTED" for item in audit) == 2
    assert not any(item["eventType"] == "PLAN_CORRECTION_COMPLETED" for item in audit)


def test_fixable_plan_error_retries_planning_and_second_attempt_proceeds(
    app: FastAPI, client: TestClient, monkeypatch
) -> None:
    original = ScriptedProvider._planning
    correction_payload: dict = {}

    def mismatched_then_corrected(payload, scenario, retry_number):
        plan = original(payload, scenario, retry_number)
        if retry_number == 0:
            return {
                **plan,
                "execution_order": [
                    task_id.replace("TASK-", "T") for task_id in plan["execution_order"]
                ],
            }
        correction_payload.update(payload)
        return plan

    monkeypatch.setattr(
        ScriptedProvider, "_planning", staticmethod(mismatched_then_corrected)
    )
    workflow = create_workflow(client, workspace="planning-correction-success")

    result = approve_pending(client, workflow)

    assert result["status"] == "WAITING_FOR_ARCHITECTURE_APPROVAL"
    checkpoint = app.state.workflow_runtime.graph.get_state(
        {"configurable": {"thread_id": workflow["threadId"]}}
    ).values
    assert checkpoint["retry_counts"]["planning"] == 1
    assert checkpoint["plan_version"] == 2
    assert correction_payload["generated_task_ids"] == [
        "TASK-001",
        "TASK-002",
        "TASK-003",
        "TASK-004",
        "TASK-005",
    ]
    assert correction_payload["execution_order"][0] == "T001"
    assert {error["code"] for error in correction_payload["validation_errors"]} >= {
        "EXECUTION_ORDER_INVALID"
    }
    assert correction_payload["approved_requirement"]
    assert correction_payload["architecture_design"]
    assert correction_payload["scenario_path_policy"]["mode"] == "TASK_SCOPED"
    assert correction_payload["post_approval_plan"] is True

    audit = client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
    assert sum(item["eventType"] == "PLAN_VALIDATION_FAILED" for item in audit) == 1
    assert sum(item["eventType"] == "PLAN_CORRECTION_STARTED" for item in audit) == 1
    assert sum(item["eventType"] == "PLAN_CORRECTION_COMPLETED" for item in audit) == 1

    with app.state.workflow_runtime.sessions() as session:
        attempts = list(
            session.scalars(
                select(AgentExecution)
                .where(
                    AgentExecution.workflow_id == workflow["workflowId"],
                    AgentExecution.agent_name == "PLANNING_AGENT",
                )
                .order_by(AgentExecution.attempt_number)
            )
        )
        tasks = list(
            session.scalars(
                select(WorkflowTask).where(
                    WorkflowTask.workflow_id == workflow["workflowId"]
                )
            )
        )
    assert [attempt.attempt_number for attempt in attempts] == [1, 2]
    assert all(attempt.status == "COMPLETED" for attempt in attempts)
    assert {task.task_key for task in tasks} == {
        "TASK-001",
        "TASK-002",
        "TASK-003",
        "TASK-004",
        "TASK-005",
    }


class SimulatedPlanningRestart(BaseException):
    pass


def test_checkpoint_restart_preserves_planning_correction_attempt(
    app: FastAPI, monkeypatch
) -> None:
    original_builder = ScriptedProvider._planning
    original_run = PlanningAgent.run
    allow_correction = False

    def first_plan_invalid(payload, scenario, retry_number):
        plan = original_builder(payload, scenario, retry_number)
        if retry_number == 0:
            return {**plan, "execution_order": ["T001", "T002", "T003", "T004", "T005"]}
        return plan

    def stop_before_correction(self, state):
        if state.get("retry_counts", {}).get("planning") == 1 and not allow_correction:
            raise SimulatedPlanningRestart()
        return original_run(self, state)

    monkeypatch.setattr(ScriptedProvider, "_planning", staticmethod(first_plan_invalid))
    monkeypatch.setattr(PlanningAgent, "run", stop_before_correction)
    with TestClient(app) as first:
        workflow = create_workflow(first, workspace="planning-correction-restart")
        pending = workflow["pendingApproval"]
        with pytest.raises(SimulatedPlanningRestart):
            app.state.workflow_service.approve(
                workflow["workflowId"],
                pending["approvalId"],
                {
                    "gateType": pending["gateType"],
                    "stateVersion": pending["stateVersion"],
                    "action": "APPROVE",
                    "comments": "Approved",
                    "conditions": [],
                    "decidedBy": "test-user",
                },
            )
        settings = app.state.workflow_runtime.settings
        checkpoint = app.state.workflow_runtime.graph.get_state(
            {"configurable": {"thread_id": workflow["threadId"]}}
        )
        assert checkpoint.values["retry_counts"]["planning"] == 1
        assert tuple(checkpoint.next) == ("planning_agent",)

    allow_correction = True
    restarted_app = create_app(settings)
    with TestClient(restarted_app):
        config = {"configurable": {"thread_id": workflow["threadId"]}}
        persisted = restarted_app.state.workflow_runtime.graph.get_state(config)
        assert persisted.values["retry_counts"]["planning"] == 1
        assert tuple(persisted.next) == ("planning_agent",)
        restarted_app.state.workflow_runtime.graph.invoke(None, config)
        resumed = restarted_app.state.workflow_service.get(workflow["workflowId"])
        assert resumed["status"] == "WAITING_FOR_ARCHITECTURE_APPROVAL"
        assert resumed["retryCounts"]["planning"] == 1
