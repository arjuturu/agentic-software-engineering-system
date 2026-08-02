from pathlib import Path

from app.config import Settings
from app.tools.command_runner import CommandRunner
from app.tools.models import ToolStatus
from app.tools.path_policy import PathPolicy
from app.tools.test_runner import TestRunner


def build_runner(tmp_path: Path) -> tuple[TestRunner, Path]:
    workspace = tmp_path / "workspace"
    repository = workspace / "project"
    repository.mkdir(parents=True)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    settings = Settings(
        _env_file=None,
        WORKSPACE_ROOT=workspace,
        ARTIFACT_ROOT=artifacts,
        MAX_COMMAND_SECONDS=30,
    )
    policy = PathPolicy(settings, project_root=tmp_path)
    return TestRunner(CommandRunner(policy, settings)), repository


def test_passing_and_failing_project_checks(tmp_path: Path) -> None:
    runner, repository = build_runner(tmp_path)
    (repository / "sample.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8"
    )
    (repository / "test_sample.py").write_text(
        "from sample import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    (repository / "pyproject.toml").write_text(
        "[tool.ruff]\ntarget-version = 'py311'\n", encoding="utf-8"
    )

    ruff = runner.run_ruff(repository)
    pytest_result = runner.run_pytest(repository)
    suite = runner.run_validation_suite(repository)

    assert ruff.status == ToolStatus.SUCCESS
    assert pytest_result.status == ToolStatus.SUCCESS
    assert suite.status == ToolStatus.SUCCESS

    (repository / "test_sample.py").write_text(
        "def test_failure():\n    assert False\n", encoding="utf-8"
    )
    failed = runner.run_pytest(repository)

    assert failed.status == ToolStatus.FAILED
    assert failed.exit_code == 1
    assert failed.error is None
    assert "failed" in failed.stdout.lower()


def test_invalid_repository_path_is_blocked(tmp_path: Path) -> None:
    runner, _repository = build_runner(tmp_path)

    result = runner.run_pytest(tmp_path)

    assert result.status == ToolStatus.BLOCKED

