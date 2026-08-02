from pathlib import Path

from app.tools.command_runner import CommandRunner
from app.tools.models import (
    CommandId,
    CommandResult,
    ToolStatus,
    ValidationSuiteResult,
)


class TestRunner:
    """Run the approved target-project quality checks."""

    __test__ = False

    def __init__(self, command_runner: CommandRunner) -> None:
        self.command_runner = command_runner

    def run_pytest(self, repository_path: Path, test_path: str | None = None) -> CommandResult:
        """Run pytest for the project or one approved relative path."""
        arguments = [test_path] if test_path else None
        return self.command_runner.run(CommandId.PYTEST, repository_path, arguments)

    def run_ruff(self, repository_path: Path) -> CommandResult:
        """Run Ruff against the complete target project."""
        return self.command_runner.run(CommandId.RUFF_CHECK, repository_path)

    def run_validation_suite(self, repository_path: Path) -> ValidationSuiteResult:
        """Run Ruff then pytest, stopping safely when Ruff cannot pass."""
        ruff = self.run_ruff(repository_path)
        if ruff.status != ToolStatus.SUCCESS:
            return ValidationSuiteResult(
                status=ToolStatus.FAILED,
                ruff=ruff,
                failed_step="RUFF_CHECK",
            )
        pytest_result = self.run_pytest(repository_path)
        status = (
            ToolStatus.SUCCESS if pytest_result.status == ToolStatus.SUCCESS else ToolStatus.FAILED
        )
        return ValidationSuiteResult(
            status=status,
            ruff=ruff,
            pytest=pytest_result,
            failed_step=None if status == ToolStatus.SUCCESS else "PYTEST",
        )
