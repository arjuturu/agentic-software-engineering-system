from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.session import get_db


def test_root_endpoint(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Agentic Software Engineering System",
        "version": "0.1.0",
        "docs": "/docs",
    }


def test_liveness(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "UP"}


def test_readiness(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "UP",
        "database": "UP",
        "artifactStorage": "UP",
        "workspace": "UP",
        "git": "UP",
        "workflowEngine": "UP",
    }


def test_readiness_returns_503_for_broken_database(app: FastAPI) -> None:
    class BrokenSession:
        def execute(self, _statement):
            raise RuntimeError("private database path must not be exposed")

    def broken_db() -> Iterator[BrokenSession]:
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_db
    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["database"] == "DOWN"
    assert response.json()["status"] == "DOWN"
    body = response.text
    assert "private database path" not in body
    assert "test.db" not in body
