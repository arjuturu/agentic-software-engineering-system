from pathlib import Path

import pytest

from app.config import Settings
from app.tools.models import ToolStatus
from app.tools.path_policy import PathPolicy, PathPolicyError
from app.tools.workspace_manager import WorkspaceManager


@pytest.fixture
def manager(tmp_path: Path) -> WorkspaceManager:
    workspace = tmp_path / "workspace"
    artifacts = tmp_path / "artifacts"
    workspace.mkdir()
    artifacts.mkdir()
    settings = Settings(
        _env_file=None, WORKSPACE_ROOT=workspace, ARTIFACT_ROOT=artifacts
    )
    return WorkspaceManager(PathPolicy(settings, project_root=tmp_path))


def test_create_and_reuse_empty_workspace(manager: WorkspaceManager) -> None:
    created = manager.create_workspace("safe-project")
    duplicate = manager.create_workspace("safe-project")

    assert created.status == ToolStatus.SUCCESS
    assert created.created is True
    assert duplicate.status == ToolStatus.SUCCESS
    assert duplicate.created is False
    assert manager.workspace_exists("safe-project")
    assert manager.ensure_workspace_is_empty("safe-project")


def test_existing_non_empty_workspace_is_rejected(manager: WorkspaceManager) -> None:
    result = manager.create_workspace("existing")
    manager.get_workspace("existing").joinpath("README.md").write_text("content", encoding="utf-8")

    duplicate = manager.create_workspace("existing")

    assert result.status == ToolStatus.SUCCESS
    assert duplicate.status == ToolStatus.BLOCKED
    assert duplicate.error is not None
    assert duplicate.error.code == "WORKSPACE_NOT_EMPTY"


@pytest.mark.parametrize(
    "name",
    ["", "../escape", "bad/name", ".hidden", "name with spaces", "CON", "a" * 81],
)
def test_invalid_workspace_names_are_rejected(
    manager: WorkspaceManager, name: str
) -> None:
    result = manager.create_workspace(name)

    assert result.status == ToolStatus.BLOCKED
    assert not manager.workspace_exists(name)


def test_get_missing_workspace_raises(manager: WorkspaceManager) -> None:
    with pytest.raises(PathPolicyError):
        manager.get_workspace("missing")


def test_list_workspaces(manager: WorkspaceManager) -> None:
    manager.create_workspace("bravo")
    manager.create_workspace("alpha")
    manager.path_policy.workspace_root.joinpath(".hidden").mkdir()

    assert manager.list_workspaces() == ["alpha", "bravo"]
