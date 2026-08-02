from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database.models import AgentExecution
from tests.phase3_helpers import create_workflow


def test_agent_runner_records_execution_and_artifacts(app: FastAPI, client: TestClient) -> None:
    workflow = create_workflow(client)
    with app.state.workflow_runtime.sessions() as session:
        count = session.scalar(select(func.count()).select_from(AgentExecution))
    assert count == 1
    artifacts = client.get(f"/api/v1/workflows/{workflow['workflowId']}/artifacts").json()
    assert {item["fileName"] for item in artifacts} >= {
        "01-requirement-analysis.json",
        "01-requirement-analysis.md",
    }
