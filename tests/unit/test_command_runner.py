import subprocess
from pathlib import Path
from typing import Any

import pytest

from app.config import Settings
from app.tools.command_runner import CommandRunner
from app.tools.models import CommandId, ToolStatus
from app.tools.path_policy import PathPolicy


@pytest.fixture
def runner_setup(tmp_path: Path) -> tuple[CommandRunner, Path]:
    workspace = tmp_path / "workspace"
    repository = workspace / "project"
    repository.mkdir(parents=True)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    settings = Settings(
        _env_file=None,
        WORKSPACE_ROOT=workspace,
        ARTIFACT_ROOT=artifacts,
        MAX_COMMAND_SECONDS=5,
        MAX_COMMAND_OUTPUT_BYTES=32,
    )
    return CommandRunner(PathPolicy(settings, project_root=tmp_path), settings), repository


def test_approved_command_executes(runner_setup: tuple[CommandRunner, Path]) -> None:
    runner, repository = runner_setup

    result = runner.run(CommandId.PYTHON_VERSION, repository)

    assert result.status == ToolStatus.SUCCESS
    assert result.exit_code == 0
    assert "Python 3.11" in result.stdout


def test_unknown_command_is_blocked(runner_setup: tuple[CommandRunner, Path]) -> None:
    runner, repository = runner_setup

    result = runner.run("SHELL", repository)  # type: ignore[arg-type]

    assert result.status == ToolStatus.BLOCKED
    assert result.error is not None
    assert result.error.code == "UNKNOWN_COMMAND"


def test_invalid_working_directory_is_blocked(
    runner_setup: tuple[CommandRunner, Path], tmp_path: Path
) -> None:
    runner, _repository = runner_setup

    result = runner.run(CommandId.PYTHON_VERSION, tmp_path)

    assert result.status == ToolStatus.BLOCKED


def test_timeout_is_structured(
    runner_setup: tuple[CommandRunner, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    runner, repository = runner_setup

    def timeout(*_args: Any, **_kwargs: Any) -> None:
        raise subprocess.TimeoutExpired(["python"], timeout=1, output="partial")

    monkeypatch.setattr(subprocess, "run", timeout)
    result = runner.run(CommandId.PYTHON_VERSION, repository, timeout_seconds=1)

    assert result.status == ToolStatus.FAILED
    assert result.timed_out is True
    assert result.error is not None
    assert result.error.code == "COMMAND_TIMEOUT"


def test_output_is_truncated_and_shell_is_false(
    runner_setup: tuple[CommandRunner, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    runner, repository = runner_setup
    captured: dict[str, Any] = {}

    def completed(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(args[0], 0, stdout="x" * 100, stderr="")

    monkeypatch.setattr(subprocess, "run", completed)
    result = runner.run(CommandId.PYTHON_VERSION, repository)

    assert result.status == ToolStatus.SUCCESS
    assert result.truncated is True
    assert len(result.stdout.encode()) <= 32
    assert captured["shell"] is False


def test_unsafe_extra_arguments_are_blocked(
    runner_setup: tuple[CommandRunner, Path],
) -> None:
    runner, repository = runner_setup

    result = runner.run(CommandId.PYTEST, repository, ["-k"])

    assert result.status == ToolStatus.BLOCKED
    assert result.error is not None
    assert result.error.code == "UNSAFE_ARGUMENT"


def test_environment_is_sanitized(
    runner_setup: tuple[CommandRunner, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, repository = runner_setup
    monkeypatch.setenv("SECRET_FOR_TEST", "must-not-leak")
    captured: dict[str, Any] = {}

    def completed(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", completed)
    runner.run(CommandId.PYTHON_VERSION, repository)

    assert "SECRET_FOR_TEST" not in captured["env"]
    assert captured["env"]["PYTHONIOENCODING"] == "utf-8"


def test_unsafe_environment_override_is_blocked(
    runner_setup: tuple[CommandRunner, Path],
) -> None:
    runner, repository = runner_setup

    result = runner.run(
        CommandId.PYTHON_VERSION,
        repository,
        safe_environment={"API_TOKEN": "private"},
    )

    assert result.status == ToolStatus.BLOCKED
    assert result.error is not None
    assert result.error.code == "UNSAFE_ENVIRONMENT"
