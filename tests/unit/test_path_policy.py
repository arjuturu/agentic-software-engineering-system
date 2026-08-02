import os
from pathlib import Path

import pytest

from app.config import Settings
from app.tools.path_policy import PathPolicy, PathPolicyError


@pytest.fixture
def policy(tmp_path: Path) -> PathPolicy:
    workspace = tmp_path / "workspace"
    artifacts = tmp_path / "artifacts"
    workspace.mkdir()
    artifacts.mkdir()
    settings = Settings(
        _env_file=None,
        WORKSPACE_ROOT=workspace,
        ARTIFACT_ROOT=artifacts,
    )
    return PathPolicy(settings, project_root=tmp_path)


def test_valid_workspace_and_artifact_paths(policy: PathPolicy) -> None:
    assert policy.resolve_workspace_path("project/src/app.py") == (
        policy.workspace_root / "project/src/app.py"
    )
    assert policy.resolve_artifact_path("WF-1001/report.md") == (
        policy.artifact_root / "WF-1001/report.md"
    )


@pytest.mark.parametrize(
    "unsafe",
    ["../escape.txt", "project/../../escape.txt", ".env", ".env.local", "secret.pem", "id_rsa"],
)
def test_unsafe_workspace_paths_are_blocked(policy: PathPolicy, unsafe: str) -> None:
    with pytest.raises(PathPolicyError):
        policy.resolve_workspace_path(unsafe)


def test_absolute_external_path_is_blocked(policy: PathPolicy, tmp_path: Path) -> None:
    with pytest.raises(PathPolicyError):
        policy.validate_write_path(tmp_path / "outside.txt")


def test_git_config_and_credentials_are_blocked(policy: PathPolicy) -> None:
    with pytest.raises(PathPolicyError):
        policy.resolve_workspace_path("project/.git/config")
    with pytest.raises(PathPolicyError):
        policy.resolve_workspace_path("project/credentials.json")


def test_normal_safe_file_is_allowed(policy: PathPolicy) -> None:
    path = policy.resolve_workspace_path("project/README.md")
    path.parent.mkdir()
    path.write_text("safe", encoding="utf-8")

    assert policy.validate_read_path(path) == path.resolve()


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symbolic links are unsupported")
def test_symlink_escape_is_blocked(policy: PathPolicy, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    link = policy.workspace_root / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symbolic link creation is not permitted on this host")

    with pytest.raises(PathPolicyError):
        policy.resolve_workspace_path("escape/secret.txt")
