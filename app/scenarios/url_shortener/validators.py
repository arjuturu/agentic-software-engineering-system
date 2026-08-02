import json
import re
from pathlib import Path

from app.scenarios.url_shortener.contract import (
    ContractCheck,
    URLShortenerContract,
    validate_openapi_routes,
)
from app.tools.alembic_runner import AlembicRunner
from app.tools.command_runner import CommandRunner
from app.tools.git_tool import GitTool
from app.tools.models import CommandId, ToolStatus
from app.tools.path_policy import PathPolicy
from app.tools.repository_scanner import RepositoryScanner
from app.tools.test_runner import TestRunner

_CONTROL_PLANE_IMPORT = re.compile(
    r"(?:from|import)\s+app\.(?:"
    r"agents|orchestration|scenarios|"
    r"services\.(?:approval_service|artifact_service|audit_service|workflow_service|"
    r"workflow_status_service)|"
    r"tools\.(?:alembic_runner|command_runner|controlled_editor|git_tool|path_policy|"
    r"repository_scanner|test_runner|workspace_manager)|"
    r"artifacts\.(?:renderer|templates|writer)"
    r")\b"
)
_DATABASE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}


class URLShortenerValidator:
    """Collect deterministic evidence for an independently generated target project."""

    def __init__(
        self,
        policy: PathPolicy,
        scanner: RepositoryScanner,
        commands: CommandRunner,
        tests: TestRunner,
        alembic: AlembicRunner,
        git: GitTool,
    ) -> None:
        self.policy = policy
        self.scanner = scanner
        self.commands = commands
        self.tests = tests
        self.alembic = alembic
        self.git = git

    def validate(self, repository_path: Path) -> URLShortenerContract:
        repository = self.policy.validate_working_directory(repository_path)
        checks: list[ContractCheck] = []
        scan = self.scanner.scan(repository)
        checks.append(
            ContractCheck(
                name="restricted_files",
                passed=not scan.restricted_files_found,
                message=(
                    "No restricted files were found."
                    if not scan.restricted_files_found
                    else "Restricted files were found."
                ),
                evidence={"files": scan.restricted_files_found},
            )
        )
        control_imports = self._control_plane_imports(repository)
        checks.append(
            ContractCheck(
                name="control_plane_independence",
                passed=not control_imports,
                message=(
                    "No control-plane imports were found."
                    if not control_imports
                    else "Control-plane imports were found."
                ),
                evidence={"files": control_imports},
            )
        )
        remotes = self.git.get_remotes(repository)
        remote_names = remotes.stdout.splitlines() if remotes.status == ToolStatus.SUCCESS else []
        checks.append(
            ContractCheck(
                name="no_git_remote",
                passed=remotes.status == ToolStatus.SUCCESS and not remote_names,
                message="Target repository has no remote."
                if not remote_names
                else "A Git remote is configured.",
                evidence={"remote_names": remote_names, "tool_status": remotes.status.value},
            )
        )
        tracked = self.git.list_tracked_files(repository)
        tracked_databases = [
            item
            for item in tracked.stdout.splitlines()
            if Path(item).suffix.lower() in _DATABASE_SUFFIXES
        ]
        checks.append(
            ContractCheck(
                name="no_committed_database",
                passed=tracked.status == ToolStatus.SUCCESS and not tracked_databases,
                message=(
                    "No database files are tracked."
                    if not tracked_databases
                    else "Database files are tracked."
                ),
                evidence={"files": tracked_databases, "tool_status": tracked.status.value},
            )
        )
        migration_files = (repository / "alembic.ini").is_file() and any(
            (repository / name / "env.py").is_file() for name in ("migrations", "alembic")
        )
        checks.append(
            ContractCheck(
                name="alembic_configuration",
                passed=migration_files,
                message="Alembic configuration exists."
                if migration_files
                else "Alembic configuration is incomplete.",
            )
        )
        import_result = self.commands.run(CommandId.TARGET_IMPORT_CHECK, repository)
        checks.append(self._command_check("target_import", import_result))
        openapi_result = self.commands.run(CommandId.TARGET_OPENAPI_CHECK, repository)
        checks.append(self._command_check("target_openapi", openapi_result))
        if openapi_result.status == ToolStatus.SUCCESS:
            try:
                checks.append(validate_openapi_routes(json.loads(openapi_result.stdout)))
            except json.JSONDecodeError:
                checks.append(
                    ContractCheck(
                        name="required_routes",
                        passed=False,
                        message="OpenAPI output was invalid JSON.",
                    )
                )
        else:
            checks.append(
                ContractCheck(
                    name="required_routes", passed=False, message="OpenAPI evidence is unavailable."
                )
            )
        suite = self.tests.run_validation_suite(repository)
        checks.append(
            ContractCheck(
                name="quality_suite",
                passed=suite.status == ToolStatus.SUCCESS,
                message="Ruff and pytest passed."
                if suite.status == ToolStatus.SUCCESS
                else "Ruff or pytest failed.",
                evidence={"failed_step": suite.failed_step},
            )
        )
        migrations = self.alembic.validate_migration_cycle(repository)
        checks.append(
            ContractCheck(
                name="migration_cycle",
                passed=migrations.status == ToolStatus.SUCCESS,
                message="Alembic cycle passed."
                if migrations.status == ToolStatus.SUCCESS
                else "Alembic cycle failed.",
                evidence={
                    "failed_step": migrations.failed_step,
                    "final_revision": migrations.final_revision,
                },
            )
        )
        return URLShortenerContract.from_checks(checks)

    @staticmethod
    def _command_check(name: str, result: object) -> ContractCheck:
        passed = result.status == ToolStatus.SUCCESS
        return ContractCheck(
            name=name,
            passed=passed,
            message=f"{name.replace('_', ' ').title()} passed."
            if passed
            else f"{name.replace('_', ' ').title()} failed.",
            evidence={"status": result.status.value, "exit_code": result.exit_code},
        )

    @staticmethod
    def _control_plane_imports(repository: Path) -> list[str]:
        findings: list[str] = []
        for path in repository.rglob("*.py"):
            if any(part in {".git", ".venv", "venv"} for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            if _CONTROL_PLANE_IMPORT.search(text):
                findings.append(path.relative_to(repository).as_posix())
        return sorted(findings)
