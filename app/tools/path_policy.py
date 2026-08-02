import fnmatch
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from app.config import Settings, get_settings
from app.core.exceptions import ApplicationError


class PathPolicyError(ApplicationError):
    """Raised when a requested path violates the tool safety policy."""

    def __init__(
        self,
        message: str,
        error_code: str = "PATH_BLOCKED",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=400,
            details=details,
        )


class PathPolicy:
    """Resolve and validate paths against canonical approved roots."""

    _RESTRICTED_NAMES = {
        "id_rsa",
        "id_ed25519",
        "credentials.json",
        "secrets.json",
    }
    _RESTRICTED_PATTERNS = ("*.pem", "*.key")
    _DEVICE_PREFIXES = ("\\\\.\\", "\\\\?\\globalroot", "\\device\\")
    _WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        project_root: Path | None = None,
        workspace_root: Path | None = None,
        artifact_root: Path | None = None,
    ) -> None:
        active_settings = settings or get_settings()
        self.project_root = (project_root or Path.cwd()).resolve()
        self.workspace_root = (workspace_root or active_settings.WORKSPACE_ROOT).resolve()
        self.artifact_root = (artifact_root or active_settings.ARTIFACT_ROOT).resolve()
        self.allowed_roots = (self.workspace_root, self.artifact_root)

    @staticmethod
    def _contains(root: Path, candidate: Path) -> bool:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            return False

    @classmethod
    def _validate_raw_path(cls, raw_path: str) -> None:
        if not raw_path or not raw_path.strip():
            raise PathPolicyError("Empty paths are not permitted.", "EMPTY_PATH")
        if "\x00" in raw_path:
            raise PathPolicyError("Paths containing null bytes are not permitted.", "NULL_BYTE")
        normalized = raw_path.replace("\\", "/")
        if any(part == ".." for part in normalized.split("/")):
            raise PathPolicyError("Parent path traversal is not permitted.", "PATH_TRAVERSAL")
        lowered = raw_path.lower()
        if any(lowered.startswith(prefix) for prefix in cls._DEVICE_PREFIXES):
            raise PathPolicyError("Device and system paths are not permitted.", "DEVICE_PATH")

    @classmethod
    def normalize_relative_path(cls, raw_path: str) -> str:
        """Return one strict workspace-relative POSIX representation for an edit path."""
        cls._validate_raw_path(raw_path)
        portable = raw_path.replace("\\", "/")
        if (
            portable.startswith("/")
            or Path(raw_path).is_absolute()
            or cls._WINDOWS_ABSOLUTE.match(raw_path)
        ):
            raise PathPolicyError("Relative paths are required.", "ABSOLUTE_PATH")
        normalized = PurePosixPath(portable).as_posix()
        if normalized in {"", "."}:
            raise PathPolicyError("Empty paths are not permitted.", "EMPTY_PATH")
        return normalized

    @classmethod
    def normalize_policy_path(cls, raw_path: str) -> str:
        """Normalize an allowlist entry; one leading slash means the workspace root."""
        cls._validate_raw_path(raw_path)
        portable = raw_path.replace("\\", "/")
        if (
            portable.startswith("//")
            or Path(raw_path).drive
            or cls._WINDOWS_ABSOLUTE.match(raw_path)
        ):
            raise PathPolicyError("Policy paths must be workspace-relative.", "ABSOLUTE_PATH")
        portable = portable.removeprefix("/")
        normalized = PurePosixPath(portable).as_posix()
        if normalized in {"", "."}:
            raise PathPolicyError("Empty paths are not permitted.", "EMPTY_PATH")
        return normalized

    @classmethod
    def normalize_policy_paths(cls, paths: list[str]) -> list[str]:
        return sorted({cls.normalize_policy_path(path) for path in paths})

    @staticmethod
    def _matches_allowed_path(candidate: str, allowed: str) -> bool:
        return candidate == allowed or candidate.startswith(f"{allowed}/")

    @classmethod
    def resolve_effective_allowed_paths(
        cls,
        task_allowed_paths: list[str],
        scenario_allowed_paths: list[str],
        *,
        policy_mode: str | None = None,
    ) -> list[str]:
        """Apply task scope and any non-empty scenario restriction deterministically."""
        task_paths = cls.normalize_policy_paths(task_allowed_paths)
        scenario_paths = cls.normalize_policy_paths(scenario_allowed_paths)
        if str(policy_mode or "").upper() == "DENY_ALL":
            return []
        if not scenario_paths:
            return task_paths
        effective: set[str] = set()
        for task_path in task_paths:
            for scenario_path in scenario_paths:
                if cls._matches_allowed_path(task_path, scenario_path):
                    effective.add(task_path)
                elif cls._matches_allowed_path(scenario_path, task_path):
                    effective.add(scenario_path)
        return sorted(effective)

    @classmethod
    def validate_allowed_path(cls, raw_path: str, effective_allowed_paths: list[str]) -> str:
        normalized = cls.normalize_relative_path(raw_path)
        if not any(
            cls._matches_allowed_path(normalized, allowed)
            for allowed in effective_allowed_paths
        ):
            raise PathPolicyError(
                "The edit path is not approved.",
                "REPOSITORY_POLICY_VIOLATION",
                details={
                    "attempted_path": normalized,
                    "normalized_path": normalized,
                    "effective_allowed_paths": effective_allowed_paths,
                    "policy_rule": "EFFECTIVE_ALLOWED_PATHS",
                },
            )
        return normalized
    def _canonical_under(self, path: Path, roots: tuple[Path, ...] | None = None) -> Path:
        self._validate_raw_path(str(path))
        try:
            resolved = path.resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise PathPolicyError("The path could not be resolved safely.") from exc
        approved = roots or self.allowed_roots
        if not any(self._contains(root, resolved) for root in approved):
            raise PathPolicyError("The path is outside the approved roots.", "OUTSIDE_ALLOWED_ROOT")
        return resolved

    def is_restricted(self, path: Path) -> bool:
        """Return whether a path matches a restricted credential or secret pattern."""
        parts = [part.lower() for part in path.parts]
        for index, part in enumerate(parts):
            if part == ".git" and index + 1 < len(parts):
                if parts[index + 1] in {"config", "credentials"}:
                    return True
        if path.name == ".env.example":
            return False
        name = path.name.lower()
        if name == ".env" or name.startswith(".env."):
            return True
        if name in self._RESTRICTED_NAMES:
            return True
        return any(fnmatch.fnmatch(name, pattern) for pattern in self._RESTRICTED_PATTERNS)

    def resolve_workspace_path(self, relative_path: str) -> Path:
        """Resolve a workspace-relative path without allowing escape or secrets."""
        self._validate_raw_path(relative_path)
        relative = Path(self.normalize_relative_path(relative_path))
        if relative.is_absolute():
            raise PathPolicyError("Workspace paths must be relative.", "ABSOLUTE_PATH")
        candidate = self._canonical_under(self.workspace_root / relative, (self.workspace_root,))
        if self.is_restricted(candidate.relative_to(self.workspace_root)):
            raise PathPolicyError("The requested path is restricted.", "RESTRICTED_PATH")
        return candidate

    def resolve_artifact_path(self, relative_path: str) -> Path:
        """Resolve an artifact-relative path without allowing escape or secrets."""
        self._validate_raw_path(relative_path)
        relative = Path(self.normalize_relative_path(relative_path))
        if relative.is_absolute():
            raise PathPolicyError("Artifact paths must be relative.", "ABSOLUTE_PATH")
        candidate = self._canonical_under(self.artifact_root / relative, (self.artifact_root,))
        if self.is_restricted(candidate.relative_to(self.artifact_root)):
            raise PathPolicyError("The requested path is restricted.", "RESTRICTED_PATH")
        return candidate

    def validate_relative_path(
        self,
        root: Path,
        relative_path: str,
        *,
        operation: Literal["read", "write"] = "read",
    ) -> Path:
        """Resolve a relative path beneath an already approved root."""
        approved_root = self._canonical_under(root)
        self._validate_raw_path(relative_path)
        relative = Path(relative_path)
        if relative.is_absolute():
            raise PathPolicyError("Relative paths are required.", "ABSOLUTE_PATH")
        candidate = self._canonical_under(approved_root / relative, (approved_root,))
        if self.is_restricted(candidate.relative_to(approved_root)):
            raise PathPolicyError("The requested path is restricted.", "RESTRICTED_PATH")
        if operation == "read" and not candidate.exists():
            raise PathPolicyError("The requested file does not exist.", "PATH_NOT_FOUND")
        return candidate

    def validate_read_path(self, path: Path) -> Path:
        """Validate an existing readable path beneath an approved root."""
        candidate = self._canonical_under(path)
        root = next(root for root in self.allowed_roots if self._contains(root, candidate))
        if self.is_restricted(candidate.relative_to(root)):
            raise PathPolicyError("The requested path is restricted.", "RESTRICTED_PATH")
        if not candidate.exists():
            raise PathPolicyError("The requested path does not exist.", "PATH_NOT_FOUND")
        return candidate

    def validate_write_path(self, path: Path) -> Path:
        """Validate a destination beneath an approved root."""
        candidate = self._canonical_under(path)
        root = next(root for root in self.allowed_roots if self._contains(root, candidate))
        if self.is_restricted(candidate.relative_to(root)):
            raise PathPolicyError("The requested path is restricted.", "RESTRICTED_PATH")
        return candidate

    def validate_working_directory(self, path: Path) -> Path:
        """Validate an existing target workspace directory."""
        candidate = self._canonical_under(path, (self.workspace_root,))
        if not candidate.is_dir():
            raise PathPolicyError(
                "The working directory does not exist.", "INVALID_WORKING_DIRECTORY"
            )
        if candidate.is_symlink():
            resolved = candidate.resolve()
            if not self._contains(self.workspace_root, resolved):
                raise PathPolicyError("The working directory link escapes the workspace.")
        if not os.access(candidate, os.R_OK | os.W_OK):
            raise PathPolicyError(
                "The working directory is not accessible.", "INACCESSIBLE_WORKING_DIRECTORY"
            )
        return candidate
