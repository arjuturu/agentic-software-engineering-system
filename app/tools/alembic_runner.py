import re
from pathlib import Path

from app.tools.command_runner import CommandRunner
from app.tools.models import (
    CommandId,
    CommandResult,
    MigrationValidationResult,
    ToolStatus,
)

_REVISION_PATTERN = re.compile(r"^([0-9A-Za-z_]+)(?:\s+\(head\))?", re.MULTILINE)


class AlembicRunner:
    """Run fixed-revision Alembic operations for a target project."""

    def __init__(self, command_runner: CommandRunner) -> None:
        self.command_runner = command_runner

    def current(self, repository_path: Path) -> CommandResult:
        """Read the current migration revision."""
        return self.command_runner.run(CommandId.ALEMBIC_CURRENT, repository_path)

    def history(self, repository_path: Path) -> CommandResult:
        """Read migration history."""
        return self.command_runner.run(CommandId.ALEMBIC_HISTORY, repository_path)

    def upgrade_head(self, repository_path: Path) -> CommandResult:
        """Upgrade the target database to its fixed head revision."""
        return self.command_runner.run(CommandId.ALEMBIC_UPGRADE_HEAD, repository_path)

    def downgrade_base(self, repository_path: Path) -> CommandResult:
        """Downgrade the target database to its fixed base revision."""
        return self.command_runner.run(CommandId.ALEMBIC_DOWNGRADE_BASE, repository_path)

    def validate_migration_cycle(self, repository_path: Path) -> MigrationValidationResult:
        """Run upgrade, downgrade, re-upgrade, and current in a fixed safe sequence."""
        sequence = [
            ("ALEMBIC_UPGRADE_HEAD", self.upgrade_head),
            ("ALEMBIC_DOWNGRADE_BASE", self.downgrade_base),
            ("ALEMBIC_UPGRADE_HEAD", self.upgrade_head),
            ("ALEMBIC_CURRENT", self.current),
        ]
        results: list[CommandResult] = []
        for name, operation in sequence:
            result = operation(repository_path)
            results.append(result)
            if result.status != ToolStatus.SUCCESS:
                return MigrationValidationResult(
                    status=ToolStatus.FAILED,
                    steps=results,
                    failed_step=name,
                )
        match = _REVISION_PATTERN.search(results[-1].stdout)
        return MigrationValidationResult(
            status=ToolStatus.SUCCESS,
            steps=results,
            final_revision=match.group(1) if match else None,
        )
