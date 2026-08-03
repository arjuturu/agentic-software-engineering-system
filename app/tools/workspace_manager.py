import logging
import re
import shutil
import tempfile
from pathlib import Path

from app.tools.models import ToolError, ToolStatus, WorkspaceResult
from app.tools.path_policy import PathPolicy, PathPolicyError

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """Create and inspect isolated target-application workspaces."""

    _NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$")
    _RESERVED_NAMES = {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{number}" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
    }

    def __init__(self, path_policy: PathPolicy) -> None:
        self.path_policy = path_policy

    @classmethod
    def _validate_name(cls, name: str) -> None:
        if (
            not name
            or name.startswith(".")
            or ".." in name
            or not cls._NAME_PATTERN.fullmatch(name)
            or name.split(".", 1)[0].lower() in cls._RESERVED_NAMES
        ):
            raise PathPolicyError("The workspace name is invalid.", "INVALID_WORKSPACE_NAME")

    def create_workspace(self, name: str) -> WorkspaceResult:
        """Create an empty workspace, without overwriting content or initializing Git."""
        try:
            self._validate_name(name)
            path = self.path_policy.resolve_workspace_path(name)
            if path.exists():
                if not path.is_dir() or any(path.iterdir()):
                    return WorkspaceResult(
                        name=name,
                        path=name,
                        status=ToolStatus.BLOCKED,
                        error=ToolError(
                            code="WORKSPACE_NOT_EMPTY",
                            message="The workspace already exists and is not empty.",
                        ),
                    )
                return WorkspaceResult(
                    name=name, path=name, status=ToolStatus.SUCCESS, created=False
                )
            path.mkdir(parents=True, exist_ok=False)
            logger.info("tool=workspace_manager operation=create status=SUCCESS workspace=%s", name)
            return WorkspaceResult(name=name, path=name, status=ToolStatus.SUCCESS, created=True)
        except (PathPolicyError, OSError) as exc:
            code = exc.error_code if isinstance(exc, PathPolicyError) else "WORKSPACE_CREATE_FAILED"
            logger.warning(
                "tool=workspace_manager operation=create status=BLOCKED error_code=%s", code
            )
            return WorkspaceResult(
                name=name,
                path=name,
                status=ToolStatus.BLOCKED,
                error=ToolError(code=code, message="The workspace could not be created."),
            )

    def validate_brownfield_source(self, source_name: str, destination_name: str) -> Path:
        """Validate an existing local repository and a distinct new destination."""
        self._validate_name(source_name)
        self._validate_name(destination_name)
        if source_name.casefold() == destination_name.casefold():
            raise PathPolicyError(
                "Source and destination workspaces must differ.", "SOURCE_EQUALS_DESTINATION"
            )
        source = self.path_policy.resolve_workspace_path(source_name)
        if source.is_symlink() or not source.is_dir():
            raise PathPolicyError(
                "The Brownfield source workspace was not found.", "SOURCE_WORKSPACE_NOT_FOUND"
            )
        source = self.path_policy.validate_working_directory(source)
        if not (source / ".git").is_dir():
            raise PathPolicyError(
                "The Brownfield source is not a local repository.", "SOURCE_NOT_REPOSITORY"
            )
        if any(path.is_symlink() for path in source.rglob("*")):
            raise PathPolicyError(
                "Symbolic links are not accepted in Brownfield sources.", "SOURCE_SYMLINK_BLOCKED"
            )
        destination = self.path_policy.resolve_workspace_path(destination_name)
        if destination.exists():
            raise PathPolicyError(
                "The destination workspace already exists.", "DESTINATION_EXISTS"
            )
        return source

    @staticmethod
    def _copy_ignored(_directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        blocked_directories = {
            ".git",
            ".venv",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            "logs",
        }
        for name in names:
            lowered = name.casefold()
            if lowered in blocked_directories:
                ignored.add(name)
                continue
            if lowered == ".env" or (
                lowered.startswith(".env.") and lowered != ".env.example"
            ):
                ignored.add(name)
                continue
            if (
                lowered.endswith((".pyc", ".db", ".sqlite", ".sqlite3", ".tmp", ".temp"))
                or lowered.startswith("~")
            ):
                ignored.add(name)
        return ignored

    def copy_brownfield_workspace(
        self, source_name: str, destination_name: str
    ) -> WorkspaceResult:
        """Copy a validated repository baseline without Git or runtime artifacts."""
        temporary: Path | None = None
        try:
            source = self.validate_brownfield_source(source_name, destination_name)
            root = self.path_policy.workspace_root
            temporary = Path(tempfile.mkdtemp(prefix=".brownfield-copy-", dir=root))
            shutil.copytree(
                source,
                temporary,
                dirs_exist_ok=True,
                ignore=self._copy_ignored,
                copy_function=shutil.copy2,
            )
            destination = self.path_policy.resolve_workspace_path(destination_name)
            temporary.replace(destination)
            temporary = None
            return WorkspaceResult(
                name=destination_name,
                path=destination_name,
                status=ToolStatus.SUCCESS,
                created=True,
            )
        except (PathPolicyError, OSError) as exc:
            code = exc.error_code if isinstance(exc, PathPolicyError) else "WORKSPACE_COPY_FAILED"
            return WorkspaceResult(
                name=destination_name,
                path=destination_name,
                status=ToolStatus.BLOCKED,
                error=ToolError(code=code, message="The Brownfield workspace could not be copied."),
            )
        finally:
            if temporary is not None and temporary.exists():
                shutil.rmtree(temporary)

    def get_workspace(self, name: str) -> Path:
        """Return an existing validated workspace path."""
        self._validate_name(name)
        path = self.path_policy.resolve_workspace_path(name)
        return self.path_policy.validate_working_directory(path)

    def workspace_exists(self, name: str) -> bool:
        """Return whether a valid workspace directory exists."""
        try:
            self._validate_name(name)
            return self.path_policy.resolve_workspace_path(name).is_dir()
        except PathPolicyError:
            return False

    def ensure_workspace_is_empty(self, name: str) -> bool:
        """Return whether an existing workspace contains no entries."""
        path = self.get_workspace(name)
        return not any(path.iterdir())

    def list_workspaces(self) -> list[str]:
        """List safe workspace directories without following symbolic links."""
        root = self.path_policy.workspace_root
        if not root.exists():
            return []
        workspaces: list[str] = []
        for path in root.iterdir():
            if path.is_symlink() or not path.is_dir():
                continue
            try:
                self._validate_name(path.name)
                self.path_policy.validate_working_directory(path)
            except PathPolicyError:
                continue
            workspaces.append(path.name)
        return sorted(workspaces)
