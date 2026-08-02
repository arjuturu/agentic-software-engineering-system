import subprocess
from pathlib import Path

import pytest

from app.config import Settings
from app.tools.git_tool import GitTool
from app.tools.models import ToolStatus
from app.tools.path_policy import PathPolicy


def configure_identity(repository: Path) -> None:
    for key, value in (
        ("user.name", "Test User"),
        ("user.email", "test@example.invalid"),
    ):
        subprocess.run(
            ["git", "-C", str(repository), "config", key, value],
            check=True,
            capture_output=True,
            text=True,
            shell=False,
            timeout=10,
        )


@pytest.fixture
def git_setup(tmp_path: Path) -> tuple[GitTool, Path]:
    workspace = tmp_path / "workspace"
    repository = workspace / "project"
    repository.mkdir(parents=True)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    settings = Settings(
        _env_file=None,
        WORKSPACE_ROOT=workspace,
        ARTIFACT_ROOT=artifacts,
        MAX_COMMAND_SECONDS=10,
    )
    return GitTool(PathPolicy(settings, project_root=tmp_path), settings), repository


def test_local_git_lifecycle_and_safe_restore(
    git_setup: tuple[GitTool, Path],
) -> None:
    git, repository = git_setup

    initialized = git.initialize_repository(repository)
    assert initialized.status == ToolStatus.SUCCESS
    assert initialized.current_branch == "main"
    configure_identity(repository)

    remotes = subprocess.run(
        ["git", "-C", str(repository), "remote"],
        check=True,
        capture_output=True,
        text=True,
        shell=False,
        timeout=10,
    )
    assert remotes.stdout == ""

    tracked = repository / "README.md"
    tracked.write_text("baseline\n", encoding="utf-8")
    assert git.get_status(repository).status == ToolStatus.SUCCESS
    assert git.stage_files(repository, ["README.md"]).status == ToolStatus.SUCCESS
    baseline = git.commit(repository, "Baseline")
    assert baseline.status == ToolStatus.SUCCESS
    assert baseline.commit_id is not None

    branch = git.create_branch(repository, "agent/WF-1001-feature")
    assert branch.status == ToolStatus.SUCCESS
    assert branch.current_branch == "agent/WF-1001-feature"

    tracked.write_text("changed\n", encoding="utf-8")
    diff = git.get_diff(repository)
    assert diff.status == ToolStatus.SUCCESS
    assert "-baseline" in diff.stdout
    assert "+changed" in diff.stdout

    assert git.stage_files(repository, ["README.md"]).status == ToolStatus.SUCCESS
    second = git.commit(repository, "Change README")
    assert second.status == ToolStatus.SUCCESS
    assert second.commit_id != baseline.commit_id

    untracked = repository / "keep.txt"
    untracked.write_text("keep", encoding="utf-8")
    restored = git.restore_to_commit(repository, baseline.commit_id)
    assert restored.status == ToolStatus.SUCCESS
    assert tracked.read_text(encoding="utf-8") == "baseline\n"
    assert untracked.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize(
    "branch_name",
    [
        "bad branch",
        "bad..branch",
        "bad~branch",
        "bad^branch",
        "bad:branch",
        "bad?branch",
        "bad*branch",
        "bad[branch",
        "bad\\branch",
        "bad/",
        "bad.lock",
    ],
)
def test_invalid_branch_names_are_blocked(
    git_setup: tuple[GitTool, Path], branch_name: str
) -> None:
    git, repository = git_setup
    assert git.initialize_repository(repository).status == ToolStatus.SUCCESS

    result = git.create_branch(repository, branch_name)

    assert result.status == ToolStatus.BLOCKED
    assert result.error is not None
    assert result.error.code == "INVALID_BRANCH"


def test_missing_stage_path_and_control_commit_message_are_blocked(
    git_setup: tuple[GitTool, Path],
) -> None:
    git, repository = git_setup
    assert git.initialize_repository(repository).status == ToolStatus.SUCCESS

    missing = git.stage_files(repository, ["missing.py"])
    control_message = git.commit(repository, "bad\nmessage")

    assert missing.status == ToolStatus.BLOCKED
    assert missing.error is not None
    assert missing.error.code == "INVALID_STAGE_PATH"
    assert control_message.status == ToolStatus.BLOCKED
    assert control_message.error is not None
    assert control_message.error.code == "INVALID_COMMIT_MESSAGE"
