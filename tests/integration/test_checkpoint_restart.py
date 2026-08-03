from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.models import WorkflowRun
from app.main import create_app
from tests.phase3_helpers import approve_pending, create_workflow


def test_file_checkpoint_survives_runtime_restart(app: FastAPI) -> None:
    with TestClient(app) as first:
        workflow = create_workflow(first, workspace="restart-target")
        thread_id = workflow["threadId"]
    with TestClient(app) as second:
        resumed = approve_pending(second, workflow)
        assert resumed["threadId"] == thread_id
        assert resumed["status"] == "WAITING_FOR_ARCHITECTURE_APPROVAL"


def test_clarification_checkpoint_survives_new_application_instance(app: FastAPI) -> None:
    with TestClient(app) as first:
        workflow = create_workflow(first, "CLARIFICATION_REQUIRED", "clarification-restart-target")
        settings = app.state.workflow_runtime.settings
        checkpoint = app.state.workflow_runtime.graph.get_state(
            {"configurable": {"thread_id": workflow["threadId"]}}
        ).values
        with app.state.workflow_runtime.sessions() as session:
            row = session.get(WorkflowRun, workflow["workflowId"])
            assert row is not None
            assert row.state_version == checkpoint["state_version"] == workflow["stateVersion"]

    restarted_app = create_app(settings)
    with TestClient(restarted_app) as restarted:
        persisted = restarted.get(f"/api/v1/workflows/{workflow['workflowId']}")
        assert persisted.status_code == 200
        waiting = persisted.json()
        assert waiting["stateVersion"] == waiting["pendingInteraction"]["payload"]["stateVersion"]
        questions = waiting["pendingInteraction"]["payload"]["questions"]
        response = restarted.post(
            f"/api/v1/workflows/{workflow['workflowId']}/clarifications",
            json={
                "workflowId": waiting["workflowId"],
                "clarificationId": waiting["pendingInteraction"]["payload"]["clarificationId"],
                "stateVersion": waiting["stateVersion"],
                "answers": [
                    {
                        "questionId": question["question_id"],
                        "answer": "Use a synchronous local implementation.",
                    }
                    for question in questions
                ],
            },
        )
        assert response.status_code == 200, response.text
        resumed = response.json()
        assert resumed["status"] == "WAITING_FOR_REQUIREMENT_APPROVAL"
        checkpoint = restarted_app.state.workflow_runtime.graph.get_state(
            {"configurable": {"thread_id": resumed["threadId"]}}
        ).values
        with restarted_app.state.workflow_runtime.sessions() as session:
            row = session.get(WorkflowRun, resumed["workflowId"])
            assert row is not None
            assert row.state_version == checkpoint["state_version"] == resumed["stateVersion"]
