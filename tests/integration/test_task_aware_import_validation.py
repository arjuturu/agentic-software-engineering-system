from pathlib import Path

import pytest

from app.config import Settings
from app.tools.command_runner import CommandRunner
from app.tools.models import CommandId, ToolStatus
from app.tools.path_policy import PathPolicy
from app.tools.test_runner import TestRunner


@pytest.fixture
def validation_target(tmp_path: Path) -> tuple[TestRunner, CommandRunner, Path]:
    workspace = tmp_path / "workspace"
    repository = workspace / "target"
    (repository / "app").mkdir(parents=True)
    (repository / "app" / "__init__.py").write_text("", encoding="utf-8")
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    settings = Settings(
        _env_file=None,
        WORKSPACE_ROOT=workspace,
        ARTIFACT_ROOT=artifacts,
        MAX_COMMAND_SECONDS=20,
    )
    commands = CommandRunner(PathPolicy(settings, project_root=tmp_path), settings)
    return TestRunner(commands), commands, repository


def _task(task_id: str, expected_files: list[str], allowed_paths: list[str]) -> dict:
    return {
        "task_id": task_id,
        "expected_files": expected_files,
        "allowed_paths": allowed_paths,
        "validation_commands": ["TARGET_IMPORT_CHECK"],
    }


def _write_modules(repository: Path, paths: list[str]) -> None:
    for relative_path in paths:
        target = repository / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("VALUE = True\n", encoding="utf-8")


@pytest.mark.parametrize(
    ("task", "expected_modules"),
    [
        (
            _task(
                "TASK-002",
                ["app/database.py", "app/models.py"],
                ["app/database.py", "app/models.py"],
            ),
            ["app.database", "app.models"],
        ),
        (
            _task(
                "TASK-003",
                ["app/schemas.py", "app/short_code_generator.py"],
                ["app/schemas.py", "app/short_code_generator.py"],
            ),
            ["app.schemas", "app.short_code_generator"],
        ),
        (
            _task(
                "TASK-004",
                ["app/repository.py", "app/service.py"],
                ["app/repository.py", "app/service.py"],
            ),
            ["app.repository", "app.service"],
        ),
    ],
)
def test_intermediate_tasks_import_only_owned_modules(
    validation_target: tuple[TestRunner, CommandRunner, Path],
    task: dict,
    expected_modules: list[str],
) -> None:
    tests, _commands, repository = validation_target
    _write_modules(repository, task["expected_files"])
    modules = tests.task_import_modules(task, task["expected_files"])

    results = tests.run_task_commands(
        repository, task["validation_commands"], import_modules=modules
    )

    assert modules == expected_modules
    assert results[0].status == ToolStatus.SUCCESS
    assert "app.main" not in results[0].stdout


def test_integration_task_imports_app_main_when_it_owns_the_file(
    validation_target: tuple[TestRunner, CommandRunner, Path],
) -> None:
    tests, _commands, repository = validation_target
    (repository / "app" / "main.py").write_text("VALUE = True\n", encoding="utf-8")
    task = _task("TASK-005", ["app/main.py"], ["app/main.py"])
    modules = tests.task_import_modules(task, ["app/main.py"])

    result = tests.run_task_commands(
        repository, task["validation_commands"], import_modules=modules
    )[0]

    assert modules == ["app.main"]
    assert result.status == ToolStatus.SUCCESS


def test_final_import_validation_still_requires_app_main(
    validation_target: tuple[TestRunner, CommandRunner, Path],
) -> None:
    _tests, commands, repository = validation_target

    missing = commands.run(CommandId.TARGET_IMPORT_CHECK, repository)
    (repository / "app" / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )
    present = commands.run(CommandId.TARGET_IMPORT_CHECK, repository)

    assert missing.status == ToolStatus.FAILED
    assert present.status == ToolStatus.SUCCESS


def test_owned_module_import_failure_is_not_skipped(
    validation_target: tuple[TestRunner, CommandRunner, Path],
) -> None:
    tests, _commands, repository = validation_target
    (repository / "app" / "models.py").write_text("def broken(:\n", encoding="utf-8")
    task = _task("TASK-002", ["app/models.py"], ["app/models.py"])

    result = tests.run_task_commands(
        repository,
        task["validation_commands"],
        import_modules=tests.task_import_modules(task, ["app/models.py"]),
    )[0]

    assert result.status == ToolStatus.FAILED


def test_openapi_check_requires_app_main(
    validation_target: tuple[TestRunner, CommandRunner, Path],
) -> None:
    _tests, commands, repository = validation_target

    result = commands.run(CommandId.TARGET_OPENAPI_CHECK, repository)

    assert result.status == ToolStatus.FAILED


def test_task_without_importable_application_modules_is_not_applicable(
    validation_target: tuple[TestRunner, CommandRunner, Path],
) -> None:
    tests, _commands, repository = validation_target
    task = _task(
        "TASK-001",
        ["pyproject.toml", "tests/test_setup.py", "alembic/versions/001.py"],
        ["pyproject.toml", "tests", "alembic"],
    )
    modules = tests.task_import_modules(task, task["expected_files"])

    result = tests.run_task_commands(
        repository, task["validation_commands"], import_modules=modules
    )[0]

    assert modules == []
    assert result.status == ToolStatus.SUCCESS
    assert "NOT_APPLICABLE" in result.stdout
