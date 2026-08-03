import hashlib
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from tests.phase3_helpers import approve_pending

GREENFIELD_REQUIREMENT = """
Build a FastAPI URL shortener with SQLite, SQLAlchemy 2.x, and Alembic.
Implement POST /api/v1/urls and GET /{short_code}. Use eight-character
secrets-based alphanumeric codes, five collision attempts, HTTP 503 on
exhaustion, HTTP 404 for missing codes, HTTP 307 redirects, Pytest, and Ruff.
"""

BROWNFIELD_REQUIREMENT = """
Enhance the existing URL-shortener application with click analytics.
Add a click_count column with default 0, increment it on successful redirects,
and add GET /api/v1/urls/{short_code}/stats. Create a new Alembic migration,
preserve existing behavior, and add regression tests.
"""

AMBIGUOUS_ALIAS_REQUIREMENT = (
    "Add support for optional custom aliases.\n\n"
    "Aliases should be user-friendly, unique, and handled safely."
)

ALIAS_ANSWERS = {
    "Q-ALIAS-001": (
        "The custom alias is optional. When omitted, retain the existing generated "
        "short-code behavior."
    ),
    "Q-ALIAS-002": "Allow lowercase letters, digits, hyphen, and underscore only.",
    "Q-ALIAS-003": "Aliases must contain between 4 and 30 characters.",
    "Q-ALIAS-004": (
        "Normalize aliases to lowercase before validation and persistence. Alias uniqueness "
        "is therefore case-insensitive. Generated short codes and aliases share the same "
        "short_code namespace."
    ),
    "Q-ALIAS-005": (
        'Return HTTP 409 with exactly: {"detail":"Custom alias already exists"}'
    ),
    "Q-ALIAS-006": "Reserve: api, docs, openapi.json, health.",
}


def create_scripted_workflow(
    client: TestClient,
    *,
    scenario_type: str,
    workspace: str,
    scripted_scenario: str,
    requirement: str,
    source: str | None = None,
) -> dict:
    payload = {
        "scenarioType": scenario_type,
        "workspaceName": workspace,
        "scriptedScenario": scripted_scenario,
        "requirement": requirement,
    }
    if source:
        payload["sourceWorkspace"] = source
    response = client.post("/api/v1/workflows", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def submit_clarification(
    client: TestClient, workflow: dict, answers: dict[str, str]
) -> dict:
    pending = workflow["pendingInteraction"]["payload"]
    response = client.post(
        f"/api/v1/workflows/{workflow['workflowId']}/clarifications",
        json={
            "workflowId": workflow["workflowId"],
            "clarificationId": pending["clarificationId"],
            "stateVersion": workflow["stateVersion"],
            "answers": [
                {"questionId": question["question_id"], "answer": answers[question["question_id"]]}
                for question in pending["questions"]
            ],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def drive_greenfield_ready(client: TestClient, workspace: str) -> dict:
    workflow = create_scripted_workflow(
        client,
        scenario_type="GREENFIELD",
        workspace=workspace,
        scripted_scenario="URL_SHORTENER_GREENFIELD_HAPPY_PATH",
        requirement=GREENFIELD_REQUIREMENT,
    )
    workflow = approve_pending(client, workflow)
    assert workflow["currentStage"] == "ARCHITECTURE_APPROVAL"
    workflow = approve_pending(client, workflow)
    assert workflow["currentStage"] == "RELEASE_APPROVAL"
    workflow = approve_pending(client, workflow)
    assert workflow["status"] == "READY"
    return workflow


def drive_source_workflow_ready(client: TestClient, workflow: dict) -> dict:
    workflow = approve_pending(client, workflow)
    assert workflow["currentStage"] == "ARCHITECTURE_APPROVAL"
    workflow = approve_pending(client, workflow)
    assert workflow["currentStage"] == "RELEASE_APPROVAL"
    workflow = approve_pending(client, workflow)
    assert workflow["status"] == "READY"
    return workflow


def snapshot_workspace(path: Path) -> dict[str, str]:
    return {
        item.relative_to(path).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(path.rglob("*"))
        if item.is_file() and ".git" not in item.relative_to(path).parts
    }


def git_output(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        shell=False,
        timeout=20,
    )
    return result.stdout.strip()
