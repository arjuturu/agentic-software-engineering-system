import json
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import get_settings

APPLICATION_TABLES = {
    "short_urls",
    "url_access_events",
    "workflow_runs",
    "workflow_requirements",
    "workflow_tasks",
    "approval_requests",
    "approval_decisions",
    "agent_executions",
    "workflow_artifacts",
    "audit_events",
}
ALL_TABLES = APPLICATION_TABLES | {"alembic_version"}


def alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def table_names(database_url: str) -> set[str]:
    engine = create_engine(database_url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_migration_upgrade_downgrade_cycle(
    tmp_path: Path, monkeypatch,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = alembic_config(database_url)

    command.upgrade(config, "head")
    assert table_names(database_url) == ALL_TABLES

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        short_url_checks = {
            item["name"] for item in inspector.get_check_constraints("short_urls")
        }
        assert "ck_short_urls_click_count_nonnegative" in short_url_checks

        workflow_uniques = {
            tuple(item["column_names"])
            for item in inspector.get_unique_constraints("workflow_requirements")
        }
        assert ("workflow_id", "version") in workflow_uniques
        assert ("workflow_id", "clarification_id") in workflow_uniques
        requirement_columns = {
            item["name"] for item in inspector.get_columns("workflow_requirements")
        }
        assert "clarification_id" in requirement_columns
        approval_uniques = {
            tuple(item["column_names"])
            for item in inspector.get_unique_constraints("approval_decisions")
        }
        assert ("approval_id",) in approval_uniques

        audit_indexes = {
            item["name"] for item in inspector.get_indexes("audit_events")
        }
        assert "ix_audit_events_workflow_id_occurred_at" in audit_indexes
        assert "ix_audit_events_event_type" in audit_indexes

        foreign_keys = inspector.get_foreign_keys("url_access_events")
        assert foreign_keys[0]["referred_table"] == "short_urls"
    finally:
        engine.dispose()

    command.downgrade(config, "base")
    assert table_names(database_url).isdisjoint(APPLICATION_TABLES)

    command.upgrade(config, "head")
    assert table_names(database_url) == ALL_TABLES
    get_settings.cache_clear()


def test_clarification_scope_migration_preserves_existing_identifier(
    tmp_path: Path, monkeypatch
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'clarification-backfill.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = alembic_config(database_url)
    command.upgrade(config, "001_initial_schema")

    now = datetime.now(UTC)
    analysis = {
        "pending_clarification": {
            "clarificationId": "CLR-1-2",
            "stateVersion": 2,
            "questions": [],
            "status": "PENDING",
        }
    }
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO workflow_runs (
                        id, thread_id, correlation_id, scenario_type, repository_path,
                        status, current_stage, state_version, started_at, updated_at
                    ) VALUES (
                        :id, :thread_id, :correlation_id, :scenario_type, :repository_path,
                        :status, :current_stage, :state_version, :started_at, :updated_at
                    )
                    """
                ),
                {
                    "id": "WF-LEGACY",
                    "thread_id": "TH-LEGACY",
                    "correlation_id": "COR-LEGACY",
                    "scenario_type": "GREENFIELD",
                    "repository_path": "workspace/legacy",
                    "status": "WAITING_FOR_CLARIFICATION",
                    "current_stage": "CLARIFICATION",
                    "state_version": 2,
                    "started_at": now,
                    "updated_at": now,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO workflow_requirements (
                        id, workflow_id, version, original_requirement, status,
                        analysis_json, created_at
                    ) VALUES (
                        :id, :workflow_id, :version, :original_requirement, :status,
                        :analysis_json, :created_at
                    )
                    """
                ),
                {
                    "id": "REQ-LEGACY",
                    "workflow_id": "WF-LEGACY",
                    "version": 1,
                    "original_requirement": "Legacy clarification",
                    "status": "CLARIFICATION_REQUIRED",
                    "analysis_json": json.dumps(analysis),
                    "created_at": now,
                },
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            clarification_id = connection.scalar(
                text(
                    "SELECT clarification_id FROM workflow_requirements "
                    "WHERE workflow_id = :workflow_id"
                ),
                {"workflow_id": "WF-LEGACY"},
            )
        assert clarification_id == "CLR-1-2"
    finally:
        engine.dispose()
        get_settings.cache_clear()
