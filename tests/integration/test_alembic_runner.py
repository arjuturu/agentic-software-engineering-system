from pathlib import Path

from app.config import Settings
from app.tools.alembic_runner import AlembicRunner
from app.tools.command_runner import CommandRunner
from app.tools.models import ToolStatus
from app.tools.path_policy import PathPolicy


def create_alembic_project(repository: Path) -> None:
    (repository / "migrations/versions").mkdir(parents=True)
    (repository / "alembic.ini").write_text(
        "[alembic]\nscript_location = migrations\nsqlalchemy.url = sqlite:///test.db\n",
        encoding="utf-8",
    )
    (repository / "migrations/env.py").write_text(
        "from alembic import context\n"
        "from sqlalchemy import engine_from_config, pool\n"
        "config = context.config\n"
        "def offline():\n"
        "    context.configure(url=config.get_main_option('sqlalchemy.url'), literal_binds=True)\n"
        "    with context.begin_transaction(): context.run_migrations()\n"
        "def online():\n"
        "    engine = engine_from_config(config.get_section(config.config_ini_section), "
        "prefix='sqlalchemy.', poolclass=pool.NullPool)\n"
        "    with engine.connect() as connection:\n"
        "        context.configure(connection=connection)\n"
        "        with context.begin_transaction(): context.run_migrations()\n"
        "offline() if context.is_offline_mode() else online()\n",
        encoding="utf-8",
    )
    (repository / "migrations/versions/001_create_demo.py").write_text(
        "from alembic import op\n"
        "import sqlalchemy as sa\n"
        "revision = '001'\n"
        "down_revision = None\n"
        "branch_labels = None\n"
        "depends_on = None\n"
        "def upgrade():\n"
        "    op.create_table('demo', sa.Column('id', sa.Integer(), primary_key=True))\n"
        "def downgrade():\n"
        "    op.drop_table('demo')\n",
        encoding="utf-8",
    )


def build_alembic_runner(tmp_path: Path) -> tuple[AlembicRunner, Path, Path]:
    workspace = tmp_path / "workspace"
    repository = workspace / "project"
    missing = workspace / "missing"
    repository.mkdir(parents=True)
    missing.mkdir()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    settings = Settings(
        _env_file=None,
        WORKSPACE_ROOT=workspace,
        ARTIFACT_ROOT=artifacts,
        MAX_COMMAND_SECONDS=30,
    )
    policy = PathPolicy(settings, project_root=tmp_path)
    return AlembicRunner(CommandRunner(policy, settings)), repository, missing


def test_alembic_operations_and_migration_cycle(tmp_path: Path) -> None:
    runner, repository, _missing = build_alembic_runner(tmp_path)
    create_alembic_project(repository)

    assert runner.upgrade_head(repository).status == ToolStatus.SUCCESS
    current = runner.current(repository)
    history = runner.history(repository)
    assert current.status == ToolStatus.SUCCESS
    assert "001" in current.stdout
    assert history.status == ToolStatus.SUCCESS
    assert "001" in history.stdout

    cycle = runner.validate_migration_cycle(repository)

    assert cycle.status == ToolStatus.SUCCESS
    assert cycle.failed_step is None
    assert cycle.final_revision == "001"
    assert len(cycle.steps) == 4


def test_missing_alembic_configuration_fails_safely(tmp_path: Path) -> None:
    runner, _repository, missing = build_alembic_runner(tmp_path)

    result = runner.upgrade_head(missing)

    assert result.status == ToolStatus.FAILED
    assert result.exit_code != 0
