from pathlib import Path

import pytest

from app.artifacts.writer import ArtifactWriter
from app.config import Settings
from app.tools.models import ToolStatus
from app.tools.path_policy import PathPolicy, PathPolicyError


@pytest.fixture
def writer(tmp_path: Path) -> ArtifactWriter:
    workspace = tmp_path / "workspace"
    artifacts = tmp_path / "artifacts"
    workspace.mkdir()
    artifacts.mkdir()
    settings = Settings(
        _env_file=None, WORKSPACE_ROOT=workspace, ARTIFACT_ROOT=artifacts
    )
    return ArtifactWriter(PathPolicy(settings, project_root=tmp_path))


def test_write_and_read_markdown(writer: ArtifactWriter) -> None:
    result = writer.write_text_artifact("WF-1001", "01-report.md", "# Report\n")

    assert result.status == ToolStatus.SUCCESS
    assert result.artifact_path == "WF-1001/01-report.md"
    assert writer.read_artifact("WF-1001", "01-report.md") == "# Report\n"


def test_write_json(writer: ArtifactWriter) -> None:
    result = writer.write_json_artifact("WF-1001", "data.json", {"b": 2, "a": 1})

    assert result.status == ToolStatus.SUCCESS
    assert writer.read_artifact("WF-1001", "data.json") == (
        '{\n  "a": 1,\n  "b": 2\n}\n'
    )


def test_overwrite_is_prevented_by_default(writer: ArtifactWriter) -> None:
    first = writer.write_text_artifact("WF-1001", "report.txt", "first")
    second = writer.write_text_artifact("WF-1001", "report.txt", "second")

    assert first.status == ToolStatus.SUCCESS
    assert second.status == ToolStatus.BLOCKED
    assert writer.read_artifact("WF-1001", "report.txt") == "first"


@pytest.mark.parametrize(
    ("workflow_id", "file_name"),
    [
        ("../WF-1001", "report.md"),
        ("invalid", "report.md"),
        ("WF-1001", "../report.md"),
        ("WF-1001", "report.py"),
        ("WF-1001", ".env"),
    ],
)
def test_invalid_artifact_paths_are_blocked(
    writer: ArtifactWriter, workflow_id: str, file_name: str
) -> None:
    result = writer.write_text_artifact(workflow_id, file_name, "blocked")

    assert result.status == ToolStatus.BLOCKED


def test_invalid_read_is_blocked(writer: ArtifactWriter) -> None:
    with pytest.raises(PathPolicyError):
        writer.read_artifact("WF-1001", "../report.md")
