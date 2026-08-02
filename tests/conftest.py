from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.database.session import create_database_engine, get_db
from app.main import create_app


@pytest.fixture
def app(tmp_path: Path) -> Iterator[FastAPI]:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    database_url = f"sqlite:///{(data_dir / 'test.db').as_posix()}"
    settings = Settings(
        _env_file=None,
        DATABASE_URL=database_url,
        LANGGRAPH_DATABASE_URL=f"sqlite:///{(data_dir / 'checkpoints.db').as_posix()}",
        WORKSPACE_ROOT=tmp_path / "workspace",
        ARTIFACT_ROOT=tmp_path / "artifacts",
        MAX_COMMAND_SECONDS=5,
    )
    test_engine = create_database_engine(database_url)
    test_session = sessionmaker(bind=test_engine, class_=Session, expire_on_commit=False)

    def override_settings() -> Settings:
        return settings

    def override_db() -> Iterator[Session]:
        with test_session() as session:
            yield session

    application = create_app()
    application.dependency_overrides[get_settings] = override_settings
    application.dependency_overrides[get_db] = override_db
    yield application
    test_engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
