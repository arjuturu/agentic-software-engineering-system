from fastapi.testclient import TestClient

from tests.phase3_helpers import create_workflow


def test_requirement_clarification_resume(client: TestClient) -> None:
    workflow = create_workflow(client, "CLARIFICATION_REQUIRED", "clarify-target")
    assert workflow["status"] == "WAITING_FOR_CLARIFICATION"
    questions = workflow["pendingInteraction"]["payload"]["questions"]
    response = client.post(
        f"/api/v1/workflows/{workflow['workflowId']}/clarifications",
        json={
            "stateVersion": workflow["stateVersion"],
            "answers": [
                {
                    "questionId": question["question_id"],
                    "answer": "Use a synchronous local implementation.",
                }
                for question in questions
            ],
        },
    )
    assert response.status_code == 200
    resumed = response.json()
    assert resumed["threadId"] == workflow["threadId"]
    assert resumed["status"] == "WAITING_FOR_REQUIREMENT_APPROVAL"
