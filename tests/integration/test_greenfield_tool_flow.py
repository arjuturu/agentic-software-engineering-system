import subprocess
from pathlib import Path

from app.artifacts.writer import ArtifactWriter
from app.config import Settings
from app.tools.controlled_editor import ControlledEditor, file_sha256
from app.tools.git_tool import GitTool
from app.tools.models import EditOperation, StructuredEdit, ToolStatus
from app.tools.path_policy import PathPolicy
from app.tools.repository_scanner import RepositoryScanner
from app.tools.workspace_manager import WorkspaceManager


def test_greenfield_controlled_tool_flow(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    artifact_root = tmp_path / "generated_artifacts"
    workspace_root.mkdir()
    artifact_root.mkdir()
    settings = Settings(
        _env_file=None,
        WORKSPACE_ROOT=workspace_root,
        ARTIFACT_ROOT=artifact_root,
        MAX_COMMAND_SECONDS=15,
    )
    policy = PathPolicy(settings, project_root=tmp_path)
    manager = WorkspaceManager(policy)
    editor = ControlledEditor(policy, settings)
    git = GitTool(policy, settings)
    scanner = RepositoryScanner(policy, settings)
    artifacts = ArtifactWriter(policy)

    workspace_result = manager.create_workspace("url-shortener-greenfield")
    assert workspace_result.status == ToolStatus.SUCCESS
    repository = manager.get_workspace("url-shortener-greenfield")

    assert git.initialize_repository(repository).status == ToolStatus.SUCCESS
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

    initial_edits = [
        StructuredEdit(
            operation=EditOperation.CREATE,
            relative_path="README.md",
            content="# Greenfield URL Shortener\n",
        ),
        StructuredEdit(
            operation=EditOperation.CREATE,
            relative_path="app.py",
            content='MESSAGE = "baseline"\n',
        ),
    ]
    created = editor.apply_batch(repository, initial_edits)
    assert created.status == ToolStatus.SUCCESS

    scan = scanner.scan(repository)
    assert "README.md" in scanner.list_files(repository)
    assert "app.py" in scanner.list_files(repository)
    assert scan.file_extensions[".py"] >= 1

    assert git.stage_files(repository, ["README.md", "app.py"]).status == ToolStatus.SUCCESS
    baseline = git.commit(repository, "Greenfield baseline")
    assert baseline.status == ToolStatus.SUCCESS

    branch = git.create_branch(repository, "agent/WF-TEST-greenfield")
    assert branch.status == ToolStatus.SUCCESS

    application_file = repository / "app.py"
    modified = editor.apply_batch(
        repository,
        [
            StructuredEdit(
                operation=EditOperation.MODIFY,
                relative_path="app.py",
                expected_hash=file_sha256(application_file),
                old_text='"baseline"',
                replacement_text='"controlled"',
            )
        ],
    )
    assert modified.status == ToolStatus.SUCCESS

    diff = git.get_diff(repository)
    assert diff.status == ToolStatus.SUCCESS
    assert '-MESSAGE = "baseline"' in diff.stdout
    assert '+MESSAGE = "controlled"' in diff.stdout

    assert git.stage_files(repository, ["app.py"]).status == ToolStatus.SUCCESS
    assert git.commit(repository, "Controlled modification").status == ToolStatus.SUCCESS

    artifact = artifacts.write_text_artifact(
        "WF-TEST", "01-greenfield-summary.md", "# Greenfield flow complete\n"
    )
    assert artifact.status == ToolStatus.SUCCESS
    assert artifacts.read_artifact("WF-TEST", "01-greenfield-summary.md").startswith(
        "# Greenfield"
    )

    for restricted_path in ("../escape.py", ".env", ".git/config"):
        blocked = editor.apply_batch(
            repository,
            [
                StructuredEdit(
                    operation=EditOperation.CREATE,
                    relative_path=restricted_path,
                    content="blocked",
                )
            ],
        )
        assert blocked.status == ToolStatus.BLOCKED

    assert not (tmp_path / "escape.py").exists()
