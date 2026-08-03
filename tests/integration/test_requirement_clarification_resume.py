from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.models import WorkflowRequirement
from app.repositories.workflow_repository import WorkflowRepository
from tests.phase3_helpers import create_workflow


def _store_versions(app: FastAPI, workflow: dict) -> tuple[int, int]:
    runtime = app.state.workflow_runtime
    graph_state = runtime.graph.get_state(
        {"configurable": {"thread_id": workflow["threadId"]}}
    ).values
    with runtime.sessions() as session:
        database_version = WorkflowRepository(session).get(workflow["workflowId"]).state_version
    return database_version, graph_state["state_version"]


def _clarification_payload(
    workflow: dict,
    state_version: int | None = None,
    answer: str = "Use a synchronous local implementation.",
) -> dict:
    pending = workflow["pendingInteraction"]["payload"]
    return {
        "workflowId": workflow["workflowId"],
        "clarificationId": pending["clarificationId"],
        "stateVersion": state_version if state_version is not None else workflow["stateVersion"],
        "answers": [
            {"questionId": question["question_id"], "answer": answer}
            for question in pending["questions"]
        ],
    }


def test_requirement_clarification_resume_versions_agree(app: FastAPI, client: TestClient) -> None:
    created = create_workflow(client, "CLARIFICATION_REQUIRED", "clarify-target")
    response = client.get(f"/api/v1/workflows/{created['workflowId']}")
    assert response.status_code == 200
    workflow = response.json()
    expected_version = workflow["pendingInteraction"]["payload"]["stateVersion"]
    database_version, checkpoint_version = _store_versions(app, workflow)
    assert workflow["stateVersion"] == expected_version
    assert database_version == expected_version
    assert checkpoint_version == expected_version

    response = client.post(
        f"/api/v1/workflows/{workflow['workflowId']}/clarifications",
        json=_clarification_payload(workflow),
    )
    assert response.status_code == 200, response.text
    resumed = response.json()
    assert resumed["threadId"] == workflow["threadId"]
    assert resumed["status"] == "WAITING_FOR_REQUIREMENT_APPROVAL"
    database_version, checkpoint_version = _store_versions(app, resumed)
    assert database_version == checkpoint_version == resumed["stateVersion"]
    assert resumed["stateVersion"] == expected_version + 2

    runtime = app.state.workflow_runtime
    with runtime.sessions() as session:
        requirement = (
            session.query(WorkflowRequirement)
            .filter_by(workflow_id=workflow["workflowId"], version=1)
            .one()
        )
        record = requirement.analysis_json["pending_clarification"]
        assert record["completedStateVersion"] == expected_version + 1
        assert len(record["answers"]) == len(_clarification_payload(workflow)["answers"])


def test_stale_clarification_version_is_rejected(client: TestClient) -> None:
    workflow = create_workflow(client, "CLARIFICATION_REQUIRED", "clarify-stale")
    response = client.post(
        f"/api/v1/workflows/{workflow['workflowId']}/clarifications",
        json=_clarification_payload(workflow, workflow["stateVersion"] - 1),
    )
    assert response.status_code == 409
    assert response.json()["errorCode"] == "INVALID_STATE_VERSION"


def test_duplicate_clarification_does_not_duplicate_answers_or_audit(
    app: FastAPI, client: TestClient
) -> None:
    workflow = create_workflow(client, "CLARIFICATION_REQUIRED", "clarify-duplicate")
    payload = _clarification_payload(workflow)
    endpoint = f"/api/v1/workflows/{workflow['workflowId']}/clarifications"
    first = client.post(endpoint, json=payload)
    assert first.status_code == 200, first.text
    duplicate = client.post(endpoint, json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["errorCode"] == "CLARIFICATION_ALREADY_SUBMITTED"

    audit = client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
    assert sum(item["eventType"] == "CLARIFICATION_SUBMITTED" for item in audit) == 1
    with app.state.workflow_runtime.sessions() as session:
        requirement = (
            session.query(WorkflowRequirement)
            .filter_by(workflow_id=workflow["workflowId"], version=1)
            .one()
        )
        record = requirement.analysis_json["pending_clarification"]
        assert record["status"] == "COMPLETED"
        assert len(record["answers"]) == len(payload["answers"])


def test_duplicate_question_ids_are_rejected_before_resume(client: TestClient) -> None:
    workflow = create_workflow(client, "CLARIFICATION_REQUIRED", "clarify-question-ids")
    payload = _clarification_payload(workflow)
    payload["answers"] = [payload["answers"][0], payload["answers"][0]]
    response = client.post(
        f"/api/v1/workflows/{workflow['workflowId']}/clarifications",
        json=payload,
    )
    assert response.status_code == 400
    assert response.json()["errorCode"] == "INVALID_CLARIFICATION_RESPONSE"
    current = client.get(f"/api/v1/workflows/{workflow['workflowId']}").json()
    assert current["status"] == "WAITING_FOR_CLARIFICATION"


def test_clarifications_with_same_id_are_isolated_by_workflow(
    app: FastAPI, client: TestClient
) -> None:
    workflow_a = create_workflow(client, "CLARIFICATION_REQUIRED", "clarify-isolation-a")
    payload_a = _clarification_payload(workflow_a, answer="Workflow A answer")
    clarification_id = payload_a["clarificationId"]
    endpoint_a = f"/api/v1/workflows/{workflow_a['workflowId']}/clarifications"
    submitted_a = client.post(endpoint_a, json=payload_a)
    assert submitted_a.status_code == 200, submitted_a.text
    resumed_a = submitted_a.json()

    workflow_b = create_workflow(client, "CLARIFICATION_REQUIRED", "clarify-isolation-b")
    payload_b = _clarification_payload(workflow_b, answer="Workflow B answer")
    assert payload_b["clarificationId"] == clarification_id
    endpoint_b = f"/api/v1/workflows/{workflow_b['workflowId']}/clarifications"

    cross_workflow = client.post(endpoint_a, json=payload_b)
    assert cross_workflow.status_code == 404
    assert cross_workflow.json()["errorCode"] == "CLARIFICATION_NOT_FOUND"

    with app.state.workflow_runtime.sessions() as session:
        requirement_a = (
            session.query(WorkflowRequirement)
            .filter_by(workflow_id=workflow_a["workflowId"], clarification_id=clarification_id)
            .one()
        )
        requirement_b = (
            session.query(WorkflowRequirement)
            .filter_by(workflow_id=workflow_b["workflowId"], clarification_id=clarification_id)
            .one()
        )
        record_a = requirement_a.analysis_json["pending_clarification"]
        record_b = requirement_b.analysis_json["pending_clarification"]
        assert record_a["answers"][0]["answer"] == "Workflow A answer"
        assert record_b["status"] == "PENDING"
        assert "answers" not in record_b

    submitted_b = client.post(endpoint_b, json=payload_b)
    assert submitted_b.status_code == 200, submitted_b.text
    resumed_b = submitted_b.json()

    duplicate_b = client.post(endpoint_b, json=payload_b)
    assert duplicate_b.status_code == 409
    assert duplicate_b.json()["errorCode"] == "CLARIFICATION_ALREADY_SUBMITTED"

    for workflow in (workflow_a, workflow_b):
        audit = client.get(f"/api/v1/workflows/{workflow['workflowId']}/audit").json()
        assert sum(item["eventType"] == "CLARIFICATION_SUBMITTED" for item in audit) == 1

    with app.state.workflow_runtime.sessions() as session:
        requirement_a = (
            session.query(WorkflowRequirement)
            .filter_by(workflow_id=workflow_a["workflowId"], clarification_id=clarification_id)
            .one()
        )
        requirement_b = (
            session.query(WorkflowRequirement)
            .filter_by(workflow_id=workflow_b["workflowId"], clarification_id=clarification_id)
            .one()
        )
        assert requirement_a.analysis_json["pending_clarification"]["answers"][0]["answer"] == (
            "Workflow A answer"
        )
        assert requirement_b.analysis_json["pending_clarification"]["answers"][0]["answer"] == (
            "Workflow B answer"
        )

    for resumed in (resumed_a, resumed_b):
        database_version, checkpoint_version = _store_versions(app, resumed)
        assert database_version == checkpoint_version == resumed["stateVersion"]
