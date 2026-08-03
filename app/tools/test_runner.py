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

    def run_task_commands(
        self,
        repository_path: Path,
        command_ids: list[str],
        *,
        import_modules: list[str] | None = None,
    ) -> list[CommandResult]:
        """Run a task's approved validation commands in declared order."""
        results: list[CommandResult] = []
        for command_id in command_ids:
            approved_id = CommandId(command_id)
            arguments = (
                import_modules if approved_id == CommandId.TARGET_IMPORT_CHECK else None
            )
            result = self.command_runner.run(
                approved_id, repository_path, extra_args=arguments
            )
            results.append(result)
            if result.status != ToolStatus.SUCCESS:
                break
        return results

    @staticmethod
    def task_import_modules(task: dict, changed_files: list[str]) -> list[str]:
        """Resolve exact application modules owned by the current coding task."""
        candidates = [
            *map(str, changed_files),
            *map(str, task.get("expected_files", [])),
            *map(str, task.get("allowed_paths", [])),
        ]
        modules: list[str] = []
        for raw_path in candidates:
            path = raw_path.replace("\\", "/").strip("/")
            parts = path.split("/")
            if (
                len(parts) < 2
                or parts[0] != "app"
                or not path.endswith(".py")
                or "__pycache__" in parts
            ):
                continue
            module_parts = parts[:-1]
            if parts[-1] != "__init__.py":
                module_parts.append(parts[-1].removesuffix(".py"))
            module = ".".join(module_parts)
            if module and module not in modules:
                modules.append(module)
        return modules
