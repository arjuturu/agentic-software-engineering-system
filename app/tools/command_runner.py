import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from app.config import Settings, get_settings
from app.tools.models import CommandId, CommandResult, ToolError, ToolStatus
from app.tools.path_policy import PathPolicy, PathPolicyError

logger = logging.getLogger(__name__)

_SECRET_KEY_MARKERS = ("SECRET", "TOKEN", "PASSWORD", "CREDENTIAL", "API_KEY", "PRIVATE_KEY")
_SAFE_BASE_ENVIRONMENT = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE")
_SAFE_EXPLICIT_ENVIRONMENT = {"APP_ENV", "DATABASE_URL", "PYTHONPATH"}
_ENVIRONMENT_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_PYTHON_MODULE_NAME = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")


class CommandRunner:
    """Execute only predefined non-interactive Python module commands."""

    def __init__(self, path_policy: PathPolicy, settings: Settings | None = None) -> None:
        active_settings = settings or get_settings()
        self.path_policy = path_policy
        self.default_timeout = active_settings.MAX_COMMAND_SECONDS
        self.max_output_bytes = active_settings.MAX_COMMAND_OUTPUT_BYTES

    @staticmethod
    def _base_arguments(command_id: CommandId) -> list[str]:
        commands = {
            CommandId.PYTEST: [sys.executable, "-m", "pytest"],
            CommandId.RUFF_CHECK: [sys.executable, "-m", "ruff", "check"],
            CommandId.ALEMBIC_CURRENT: [sys.executable, "-m", "alembic", "current"],
            CommandId.ALEMBIC_HISTORY: [sys.executable, "-m", "alembic", "history"],
            CommandId.ALEMBIC_UPGRADE_HEAD: [
                sys.executable,
                "-m",
                "alembic",
                "upgrade",
                "head",
            ],
            CommandId.ALEMBIC_DOWNGRADE_BASE: [
                sys.executable,
                "-m",
                "alembic",
                "downgrade",
                "base",
            ],
            CommandId.PYTHON_VERSION: [sys.executable, "--version"],
            CommandId.TARGET_IMPORT_CHECK: [
                sys.executable,
                "-c",
                "from app.main import app; print(app.title)",
            ],
            CommandId.TARGET_OPENAPI_CHECK: [
                sys.executable,
                "-c",
                (
                    "import json; from app.main import app; "
                    "print(json.dumps(app.openapi(), sort_keys=True))"
                ),
            ],
        }
        return list(commands[command_id])

    def _validated_arguments(
        self,
        command_id: CommandId,
        working_directory: Path,
        extra_args: list[str] | None,
    ) -> list[str]:
        if command_id == CommandId.TARGET_IMPORT_CHECK:
            if extra_args is None:
                return self._base_arguments(command_id)
            modules = list(dict.fromkeys(extra_args))
            if not modules:
                return [
                    sys.executable,
                    "-c",
                    "print('TARGET_IMPORT_CHECK_NOT_APPLICABLE')",
                ]
            if not all(_PYTHON_MODULE_NAME.fullmatch(module) for module in modules):
                raise PathPolicyError(
                    "A target module name is unsafe.", "UNSAFE_ARGUMENT"
                )
            module_tuple = repr(tuple(modules))
            return [
                sys.executable,
                "-c",
                (
                    "import importlib; "
                    f"modules = {module_tuple}; "
                    "[importlib.import_module(module) for module in modules]; "
                    "print(','.join(modules))"
                ),
            ]
        if command_id not in {CommandId.PYTEST, CommandId.RUFF_CHECK}:
            if extra_args:
                raise PathPolicyError(
                    "This command does not accept extra arguments.", "EXTRA_ARGUMENT_BLOCKED"
                )
            return self._base_arguments(command_id)
        validated_extra_args = extra_args or []
        if len(validated_extra_args) > 1:
            raise PathPolicyError(
                "Only one approved relative path is accepted.", "EXTRA_ARGUMENT_BLOCKED"
            )
        target = validated_extra_args[0] if validated_extra_args else "."
        if target.startswith("-") or any(character in target for character in (";", "|", ">", "<")):
            raise PathPolicyError("The command argument is unsafe.", "UNSAFE_ARGUMENT")
        self.path_policy.validate_relative_path(working_directory, target)
        return [*self._base_arguments(command_id), target]

    @staticmethod
    def _environment(safe_environment: dict[str, str] | None) -> dict[str, str]:
        environment = {
            name: os.environ[name] for name in _SAFE_BASE_ENVIRONMENT if name in os.environ
        }
        environment["PYTHONIOENCODING"] = "utf-8"
        if safe_environment:
            for name, value in safe_environment.items():
                upper_name = name.upper()
                if (
                    name != upper_name
                    or not _ENVIRONMENT_NAME.fullmatch(name)
                    or name not in _SAFE_EXPLICIT_ENVIRONMENT
                    or any(marker in upper_name for marker in _SECRET_KEY_MARKERS)
                    or "\x00" in value
                ):
                    raise PathPolicyError(
                        "An environment override was blocked.", "UNSAFE_ENVIRONMENT"
                    )
                environment[name] = value
        return environment

    def _truncate(self, stdout: str, stderr: str) -> tuple[str, str, bool]:
        stdout_bytes = stdout.encode("utf-8", errors="replace")
        stderr_bytes = stderr.encode("utf-8", errors="replace")
        combined = stdout_bytes + stderr_bytes
        if len(combined) <= self.max_output_bytes:
            return stdout, stderr, False
        stdout_budget = min(len(stdout_bytes), self.max_output_bytes)
        safe_stdout = stdout_bytes[:stdout_budget].decode("utf-8", errors="replace")
        remaining = self.max_output_bytes - stdout_budget
        safe_stderr = stderr_bytes[:remaining].decode("utf-8", errors="replace")
        return safe_stdout, safe_stderr, True

    @staticmethod
    def _blocked(command_id: str, code: str, message: str) -> CommandResult:
        return CommandResult(
            command_id=command_id,
            status=ToolStatus.BLOCKED,
            exit_code=None,
            stdout="",
            stderr="",
            duration_ms=0,
            error=ToolError(code=code, message=message),
        )

    def run(
        self,
        command_id: CommandId,
        working_directory: Path,
        extra_args: list[str] | None = None,
        timeout_seconds: int | None = None,
        safe_environment: dict[str, str] | None = None,
    ) -> CommandResult:
        """Execute an approved command ID in a validated target workspace."""
        command_name = command_id.value if isinstance(command_id, CommandId) else str(command_id)
        try:
            approved_id = CommandId(command_id)
            directory = self.path_policy.validate_working_directory(working_directory)
            arguments = self._validated_arguments(approved_id, directory, extra_args)
            environment = self._environment(safe_environment)
            timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout
            if timeout <= 0 or timeout > self.default_timeout:
                raise PathPolicyError("The command timeout is invalid.", "INVALID_TIMEOUT")
        except (ValueError, PathPolicyError) as exc:
            code = exc.error_code if isinstance(exc, PathPolicyError) else "UNKNOWN_COMMAND"
            logger.warning(
                "tool=command_runner operation=%s status=BLOCKED error_code=%s",
                command_name,
                code,
            )
            return self._blocked(command_name, code, "The command request was blocked.")

        started = time.monotonic()
        try:
            completed = subprocess.run(
                arguments,
                cwd=directory,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
                shell=False,
                timeout=timeout,
            )
            duration_ms = round((time.monotonic() - started) * 1000)
            stdout, stderr, truncated = self._truncate(completed.stdout, completed.stderr)
            status = ToolStatus.SUCCESS if completed.returncode == 0 else ToolStatus.FAILED
            result = CommandResult(
                command_id=approved_id.value,
                status=status,
                exit_code=completed.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
                truncated=truncated,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = round((time.monotonic() - started) * 1000)
            stdout = (
                exc.stdout.decode("utf-8", "replace")
                if isinstance(exc.stdout, bytes)
                else exc.stdout
            )
            stderr = (
                exc.stderr.decode("utf-8", "replace")
                if isinstance(exc.stderr, bytes)
                else exc.stderr
            )
            safe_stdout, safe_stderr, truncated = self._truncate(stdout or "", stderr or "")
            result = CommandResult(
                command_id=approved_id.value,
                status=ToolStatus.FAILED,
                exit_code=None,
                stdout=safe_stdout,
                stderr=safe_stderr,
                duration_ms=duration_ms,
                timed_out=True,
                truncated=truncated,
                error=ToolError(code="COMMAND_TIMEOUT", message="The approved command timed out."),
            )
        except OSError:
            duration_ms = round((time.monotonic() - started) * 1000)
            logger.exception(
                "tool=command_runner operation=%s status=FAILED error_code=EXECUTION_FAILED",
                approved_id.value,
            )
            result = CommandResult(
                command_id=approved_id.value,
                status=ToolStatus.FAILED,
                exit_code=None,
                stdout="",
                stderr="",
                duration_ms=duration_ms,
                error=ToolError(
                    code="EXECUTION_FAILED",
                    message="The approved command could not be executed.",
                ),
            )
        logger.info(
            "tool=command_runner operation=%s status=%s duration_ms=%d workspace=%s",
            approved_id.value,
            result.status.value,
            result.duration_ms,
            directory.relative_to(self.path_policy.workspace_root).as_posix(),
        )
        return result
