from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

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
