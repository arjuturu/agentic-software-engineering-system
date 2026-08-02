import logging
import os
import re
import subprocess
from pathlib import Path

from app.config import Settings, get_settings
from app.tools.models import GitOperationResult, ToolError, ToolStatus
from app.tools.path_policy import PathPolicy, PathPolicyError

logger = logging.getLogger(__name__)

_BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
_COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{7,40}$")


class GitTool:
    """Perform an allow-listed set of local-only Git operations."""

    def __init__(self, path_policy: PathPolicy, settings: Settings | None = None) -> None:
        self.path_policy = path_policy
        self.timeout = (settings or get_settings()).MAX_COMMAND_SECONDS

    def _raw(self, repository: Path, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        environment = {
            name: os.environ[name]
            for name in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE")
            if name in os.environ
        }
        environment.update(
            {
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_TERMINAL_PROMPT": "0",
            }
        )
        disabled_hooks = repository / ".disabled-git-hooks"
        return subprocess.run(
            [
                "git",
                "-c",
                f"core.hooksPath={disabled_hooks}",
                "-c",
                "commit.gpgSign=false",
                "-c",
                "user.name=Governed Workflow",
                "-c",
                "user.email=workflow@example.invalid",
                "-C",
                str(repository),
                *arguments,
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=self.timeout,
        )

    def _metadata(self, repository: Path) -> tuple[str | None, str | None, list[str]]:
        branch_result = self._raw(repository, ["branch", "--show-current"])
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
        head_result = self._raw(repository, ["rev-parse", "--verify", "HEAD"])
        commit_id = head_result.stdout.strip() if head_result.returncode == 0 else None
        status_result = self._raw(repository, ["status", "--porcelain"])
        changed = []
        if status_result.returncode == 0:
            changed = [
                line[3:].split(" -> ")[-1]
                for line in status_result.stdout.splitlines()
                if len(line) > 3
            ]
        return branch or None, commit_id or None, changed

    def _result(
        self,
        operation: str,
        repository: Path,
        completed: subprocess.CompletedProcess[str],
    ) -> GitOperationResult:
        branch, commit_id, changed = self._metadata(repository)
        status = ToolStatus.SUCCESS if completed.returncode == 0 else ToolStatus.FAILED
        error = None
        if status == ToolStatus.FAILED:
            error = ToolError(
                code="GIT_COMMAND_FAILED",
                message=f"The local Git {operation} operation failed.",
                details={"exit_code": completed.returncode},
            )
        logger.info(
            "tool=git operation=%s status=%s workspace=%s",
            operation,
            status.value,
            repository.relative_to(self.path_policy.workspace_root).as_posix(),
        )
        return GitOperationResult(
            operation=operation,
            status=status,
            current_branch=branch,
            commit_id=commit_id,
            changed_files=changed,
            stdout=completed.stdout,
            stderr=completed.stderr,
            error=error,
        )

    @staticmethod
    def _blocked(operation: str, code: str, message: str) -> GitOperationResult:
        return GitOperationResult(
            operation=operation,
            status=ToolStatus.BLOCKED,
            error=ToolError(code=code, message=message),
        )

    def _repository(self, path: Path, operation: str) -> Path | GitOperationResult:
        try:
            repository = self.path_policy.validate_working_directory(path)
        except PathPolicyError as exc:
            return self._blocked(operation, exc.error_code, "The repository path was blocked.")
        if not (repository / ".git").is_dir():
            return self._blocked(operation, "NOT_A_REPOSITORY", "No local Git repository exists.")
        return repository

    def is_repository(self, path: Path) -> bool:
        """Return whether a validated target path contains local Git metadata."""
        try:
            repository = self.path_policy.validate_working_directory(path)
        except PathPolicyError:
            return False
        return (repository / ".git").is_dir()

    def initialize_repository(self, path: Path) -> GitOperationResult:
        """Initialize a local repository and normalize its branch to main."""
        operation = "initialize"
        try:
            repository = self.path_policy.validate_working_directory(path)
            initialized = self._raw(repository, ["init"])
            if initialized.returncode != 0:
                return self._result(operation, repository, initialized)
            renamed = self._raw(repository, ["branch", "-M", "main"])
            return self._result(operation, repository, renamed)
        except PathPolicyError as exc:
            return self._blocked(
                operation, exc.error_code, "Repository initialization was blocked."
            )
        except (OSError, subprocess.SubprocessError):
            logger.exception("tool=git operation=initialize status=FAILED")
            return self._blocked(
                operation, "GIT_UNAVAILABLE", "The local Git executable could not be used."
            )

    def get_status(self, path: Path) -> GitOperationResult:
        """Return porcelain status for a local target repository."""
        operation = "status"
        repository = self._repository(path, operation)
        if isinstance(repository, GitOperationResult):
            return repository
        try:
            return self._result(operation, repository, self._raw(repository, ["status", "--short"]))
        except (OSError, subprocess.SubprocessError):
            logger.exception("tool=git operation=status status=FAILED")
            return self._blocked(operation, "GIT_UNAVAILABLE", "Git status could not be read.")

    def get_current_branch(self, path: Path) -> GitOperationResult:
        """Return the current local branch."""
        operation = "current_branch"
        repository = self._repository(path, operation)
        if isinstance(repository, GitOperationResult):
            return repository
        try:
            return self._result(
                operation, repository, self._raw(repository, ["branch", "--show-current"])
            )
        except (OSError, subprocess.SubprocessError):
            logger.exception("tool=git operation=current_branch status=FAILED")
            return self._blocked(operation, "GIT_UNAVAILABLE", "The branch could not be read.")

    def get_head_commit(self, path: Path) -> GitOperationResult:
        """Return the current HEAD commit."""
        operation = "head_commit"
        repository = self._repository(path, operation)
        if isinstance(repository, GitOperationResult):
            return repository
        try:
            return self._result(
                operation, repository, self._raw(repository, ["rev-parse", "--verify", "HEAD"])
            )
        except (OSError, subprocess.SubprocessError):
            logger.exception("tool=git operation=head_commit status=FAILED")
            return self._blocked(operation, "GIT_UNAVAILABLE", "HEAD could not be read.")

    @staticmethod
    def _valid_branch(branch_name: str) -> bool:
        return bool(
            _BRANCH_PATTERN.fullmatch(branch_name)
            and ".." not in branch_name
            and not branch_name.endswith("/")
            and not branch_name.endswith(".lock")
            and not branch_name.startswith("/")
            and "//" not in branch_name
            and "@{" not in branch_name
        )

    def create_branch(self, path: Path, branch_name: str) -> GitOperationResult:
        """Create and switch to a policy-valid local branch."""
        operation = "create_branch"
        if not self._valid_branch(branch_name):
            return self._blocked(operation, "INVALID_BRANCH", "The branch name is invalid.")
        repository = self._repository(path, operation)
        if isinstance(repository, GitOperationResult):
            return repository
        try:
            return self._result(
                operation, repository, self._raw(repository, ["checkout", "-b", branch_name])
            )
        except (OSError, subprocess.SubprocessError):
            logger.exception("tool=git operation=create_branch status=FAILED")
            return self._blocked(operation, "GIT_UNAVAILABLE", "The branch could not be created.")

    def stage_files(self, path: Path, files: list[str]) -> GitOperationResult:
        """Stage an explicit list of safe repository-relative files."""
        operation = "stage_files"
        repository = self._repository(path, operation)
        if isinstance(repository, GitOperationResult):
            return repository
        if not files:
            return self._blocked(operation, "EMPTY_FILE_LIST", "No files were provided.")
        try:
            for file_name in files:
                candidate = self.path_policy.validate_relative_path(
                    repository, file_name, operation="write"
                )
                if not candidate.is_file():
                    raise PathPolicyError(
                        "Only existing regular files can be staged.", "INVALID_STAGE_PATH"
                    )
            completed = self._raw(repository, ["add", "--", *files])
            return self._result(operation, repository, completed)
        except PathPolicyError as exc:
            return self._blocked(operation, exc.error_code, "A staged path was blocked.")
        except (OSError, subprocess.SubprocessError):
            logger.exception("tool=git operation=stage_files status=FAILED")
            return self._blocked(operation, "GIT_UNAVAILABLE", "Files could not be staged.")

    @staticmethod
    def _valid_commit_message(message: str) -> bool:
        return bool(
            message
            and len(message) <= 500
            and not any(ord(character) < 32 for character in message)
        )

    def commit(self, path: Path, message: str) -> GitOperationResult:
        """Create a local commit with a bounded non-empty message."""
        operation = "commit"
        if not self._valid_commit_message(message):
            return self._blocked(
                operation, "INVALID_COMMIT_MESSAGE", "The commit message is invalid."
            )
        repository = self._repository(path, operation)
        if isinstance(repository, GitOperationResult):
            return repository
        try:
            return self._result(
                operation, repository, self._raw(repository, ["commit", "-m", message])
            )
        except (OSError, subprocess.SubprocessError):
            logger.exception("tool=git operation=commit status=FAILED")
            return self._blocked(operation, "GIT_UNAVAILABLE", "The commit could not be created.")

    def get_diff(self, path: Path, staged: bool = False) -> GitOperationResult:
        """Return a local working-tree or staged diff."""
        operation = "diff_staged" if staged else "diff"
        repository = self._repository(path, operation)
        if isinstance(repository, GitOperationResult):
            return repository
        arguments = ["diff", "--cached", "--no-ext-diff"] if staged else ["diff", "--no-ext-diff"]
        try:
            return self._result(operation, repository, self._raw(repository, arguments))
        except (OSError, subprocess.SubprocessError):
            logger.exception("tool=git operation=diff status=FAILED")
            return self._blocked(operation, "GIT_UNAVAILABLE", "The diff could not be generated.")

    def restore_to_commit(self, path: Path, commit_id: str) -> GitOperationResult:
        """Restore tracked index and worktree files from a verified local commit."""
        operation = "restore_to_commit"
        if not _COMMIT_PATTERN.fullmatch(commit_id):
            return self._blocked(operation, "INVALID_COMMIT", "The commit identifier is invalid.")
        repository = self._repository(path, operation)
        if isinstance(repository, GitOperationResult):
            return repository
        try:
            verification = self._raw(repository, ["cat-file", "-e", f"{commit_id}^{{commit}}"])
            if verification.returncode != 0:
                return self._result(operation, repository, verification)
            restored = self._raw(
                repository,
                ["restore", "--source", commit_id, "--staged", "--worktree", "--", "."],
            )
            return self._result(operation, repository, restored)
        except (OSError, subprocess.SubprocessError):
            logger.exception("tool=git operation=restore_to_commit status=FAILED")
            return self._blocked(
                operation, "GIT_UNAVAILABLE", "Tracked files could not be restored."
            )
