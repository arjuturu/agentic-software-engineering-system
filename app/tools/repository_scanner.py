import logging
import subprocess
from collections import Counter
from pathlib import Path

from app.config import Settings, get_settings
from app.tools.models import RepositoryScanResult, ToolError, ToolStatus
from app.tools.path_policy import PathPolicy, PathPolicyError

logger = logging.getLogger(__name__)

_PROJECT_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "alembic.ini",
    "readme.md",
    "readme",
    ".gitignore",
}


class RepositoryScanner:
    """Read repository structure and small text files without importing target code."""

    def __init__(self, path_policy: PathPolicy, settings: Settings | None = None) -> None:
        self.path_policy = path_policy
        active_settings = settings or get_settings()
        self.max_files = active_settings.MAX_SCAN_FILES
        self.max_file_bytes = active_settings.MAX_SCAN_FILE_BYTES
        self.command_timeout = active_settings.MAX_COMMAND_SECONDS

    @staticmethod
    def _is_binary(path: Path) -> bool:
        try:
            with path.open("rb") as stream:
                return b"\x00" in stream.read(8192)
        except OSError:
            return True

    def _branch(self, repository: Path) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(repository), "branch", "--show-current"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                timeout=self.command_timeout,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        branch = result.stdout.strip()
        return branch or None if result.returncode == 0 else None

    def _relative_repository(self, repository: Path) -> str:
        return repository.relative_to(self.path_policy.workspace_root).as_posix()

    def scan(self, repository_path: Path) -> RepositoryScanResult:
        """Return a policy-safe structural and technology summary."""
        try:
            repository = self.path_policy.validate_working_directory(repository_path)
        except PathPolicyError as exc:
            return RepositoryScanResult(
                repository_path=".",
                status=ToolStatus.BLOCKED,
                is_git_repository=False,
                error=ToolError(code=exc.error_code, message="Repository scanning was blocked."),
            )

        files: list[str] = []
        skipped: list[str] = []
        restricted: list[str] = []
        project_files: list[str] = []
        packages: list[str] = []
        test_files: list[str] = []
        migrations: list[str] = []
        fastapi_files: list[str] = []
        sqlalchemy_files: list[str] = []
        extensions: Counter[str] = Counter()
        directory_count = 0
        limit_reached = False

        try:
            paths = sorted(repository.rglob("*"), key=lambda item: item.as_posix())
            for path in paths:
                relative = path.relative_to(repository)
                relative_text = relative.as_posix()
                if path.is_symlink():
                    skipped.append(relative_text)
                    continue
                if path.is_dir():
                    directory_count += 1
                    continue
                if not path.is_file():
                    continue
                if len(files) >= self.max_files:
                    limit_reached = True
                    skipped.append("<file-limit-reached>")
                    break
                files.append(relative_text)
                extensions[path.suffix.lower() or "<none>"] += 1

                if self.path_policy.is_restricted(relative):
                    restricted.append(relative_text)
                    skipped.append(relative_text)
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    skipped.append(relative_text)
                    continue
                if size > self.max_file_bytes or self._is_binary(path):
                    skipped.append(relative_text)
                    continue

                lowered_name = path.name.lower()
                if lowered_name in _PROJECT_FILES:
                    project_files.append(relative_text)
                if path.name == "__init__.py":
                    packages.append(relative.parent.as_posix())
                if (
                    relative.parts
                    and relative.parts[0].lower() in {"test", "tests"}
                    or path.name.lower().startswith("test_")
                ):
                    test_files.append(relative_text)
                if (
                    "migrations" in [part.lower() for part in relative.parts]
                    and path.suffix.lower() == ".py"
                ):
                    migrations.append(relative_text)

                try:
                    text = path.read_text(encoding="utf-8", errors="replace").lower()
                except OSError:
                    skipped.append(relative_text)
                    continue
                if "fastapi" in text or "fastapi" in lowered_name:
                    fastapi_files.append(relative_text)
                if "sqlalchemy" in text or "sqlalchemy" in lowered_name:
                    sqlalchemy_files.append(relative_text)
        except OSError:
            logger.exception("tool=repository_scanner operation=scan status=FAILED")
            return RepositoryScanResult(
                repository_path=self._relative_repository(repository),
                status=ToolStatus.FAILED,
                is_git_repository=False,
                error=ToolError(
                    code="SCAN_FAILED", message="The repository could not be scanned safely."
                ),
            )

        is_git = (repository / ".git").is_dir()
        status = ToolStatus.PARTIAL if skipped or limit_reached else ToolStatus.SUCCESS
        result = RepositoryScanResult(
            repository_path=self._relative_repository(repository),
            status=status,
            is_git_repository=is_git,
            current_branch=self._branch(repository) if is_git else None,
            file_count=len(files),
            directory_count=directory_count,
            file_extensions=dict(sorted(extensions.items())),
            detected_project_files=sorted(set(project_files)),
            detected_python_packages=sorted(set(packages)),
            detected_test_files=sorted(set(test_files)),
            detected_migration_files=sorted(set(migrations)),
            fastapi_files=sorted(set(fastapi_files)),
            sqlalchemy_files=sorted(set(sqlalchemy_files)),
            restricted_files_found=sorted(set(restricted)),
            skipped_files=sorted(set(skipped)),
            repository_summary=(
                f"{len(files)} files, {directory_count} directories, "
                f"{len(project_files)} project files"
            ),
        )
        logger.info(
            "tool=repository_scanner operation=scan status=%s workspace=%s",
            result.status.value,
            result.repository_path,
        )
        return result

    def list_files(self, repository_path: Path) -> list[str]:
        """List non-restricted regular files relative to a target repository."""
        repository = self.path_policy.validate_working_directory(repository_path)
        result: list[str] = []
        for path in sorted(repository.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(repository)
            if not self.path_policy.is_restricted(relative):
                result.append(relative.as_posix())
            if len(result) >= self.max_files:
                break
        return result

    def read_safe_text_file(self, repository_path: Path, relative_path: str) -> str:
        """Read a small, non-binary UTF-8 text file after full policy validation."""
        repository = self.path_policy.validate_working_directory(repository_path)
        path = self.path_policy.validate_relative_path(repository, relative_path)
        if not path.is_file():
            raise PathPolicyError("The requested path is not a file.", "NOT_A_FILE")
        if path.stat().st_size > self.max_file_bytes:
            raise PathPolicyError("The requested file exceeds the scan limit.", "FILE_TOO_LARGE")
        if self._is_binary(path):
            raise PathPolicyError("Binary files cannot be read.", "BINARY_FILE")
        return path.read_text(encoding="utf-8")
