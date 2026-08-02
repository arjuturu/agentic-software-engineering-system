from pathlib import Path

import pytest

from app.config import Settings
from app.tools.controlled_editor import ControlledEditor, file_sha256
from app.tools.models import EditOperation, StructuredEdit, ToolStatus
from app.tools.path_policy import PathPolicy


@pytest.fixture
def editor_setup(tmp_path: Path) -> tuple[ControlledEditor, Path]:
    workspace_root = tmp_path / "workspace"
    repository = workspace_root / "project"
    repository.mkdir(parents=True)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    settings = Settings(
        _env_file=None,
        WORKSPACE_ROOT=workspace_root,
        ARTIFACT_ROOT=artifacts,
        MAX_EDIT_FILE_BYTES=256,
    )
    return ControlledEditor(PathPolicy(settings, project_root=tmp_path), settings), repository


def create_edit(path: str, content: str) -> StructuredEdit:
    return StructuredEdit(
        operation=EditOperation.CREATE, relative_path=path, content=content
    )


def modify_edit(path: Path, old: str, new: str) -> StructuredEdit:
    return StructuredEdit(
        operation=EditOperation.MODIFY,
        relative_path=path.name,
        expected_hash=file_sha256(path),
        old_text=old,
        replacement_text=new,
    )


def test_create_and_reject_duplicate(
    editor_setup: tuple[ControlledEditor, Path],
) -> None:
    editor, repository = editor_setup

    created = editor.apply_batch(repository, [create_edit("README.md", "hello\n")])
    duplicate = editor.apply_batch(repository, [create_edit("README.md", "again\n")])

    assert created.status == ToolStatus.SUCCESS
    assert (repository / "README.md").read_text(encoding="utf-8") == "hello\n"
    assert duplicate.status == ToolStatus.BLOCKED
    assert duplicate.error is not None
    assert duplicate.error.code == "FILE_ALREADY_EXISTS"


def test_modify_with_hash_and_reject_stale_hash(
    editor_setup: tuple[ControlledEditor, Path],
) -> None:
    editor, repository = editor_setup
    path = repository / "app.py"
    path.write_text("value = 1\n", encoding="utf-8")

    valid = editor.apply_batch(repository, [modify_edit(path, "value = 1", "value = 2")])
    stale = StructuredEdit(
        operation=EditOperation.MODIFY,
        relative_path="app.py",
        expected_hash="0" * 64,
        old_text="value = 2",
        replacement_text="value = 3",
    )

    assert valid.status == ToolStatus.SUCCESS
    assert path.read_text(encoding="utf-8") == "value = 2\n"
    rejected = editor.apply_batch(repository, [stale])
    assert rejected.status == ToolStatus.BLOCKED
    assert path.read_text(encoding="utf-8") == "value = 2\n"


@pytest.mark.parametrize(
    ("content", "old_text", "error_code"),
    [
        ("alpha\n", "missing", "TEXT_NOT_FOUND"),
        ("same same\n", "same", "MULTIPLE_MATCHES"),
    ],
)
def test_exact_match_rules(
    editor_setup: tuple[ControlledEditor, Path],
    content: str,
    old_text: str,
    error_code: str,
) -> None:
    editor, repository = editor_setup
    path = repository / "app.py"
    path.write_text(content, encoding="utf-8")
    edit = modify_edit(path, old_text, "replacement")

    result = editor.apply_batch(repository, [edit])

    assert result.status == ToolStatus.BLOCKED
    assert result.error is not None
    assert result.error.code == error_code
    assert path.read_text(encoding="utf-8") == content


def test_atomic_rollback_when_later_write_fails(
    editor_setup: tuple[ControlledEditor, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    editor, repository = editor_setup
    original_atomic_write = editor._atomic_write
    call_count = 0

    def fail_second_write(path: Path, content: bytes) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise OSError("simulated write failure")
        original_atomic_write(path, content)

    monkeypatch.setattr(editor, "_atomic_write", fail_second_write)

    result = editor.apply_batch(
        repository,
        [create_edit("first.py", "first = True\n"), create_edit("second.py", "second = True\n")],
    )

    assert result.status == ToolStatus.FAILED
    assert result.rolled_back is True
    assert not (repository / "first.py").exists()
    assert not (repository / "second.py").exists()


@pytest.mark.parametrize(
    "path",
    [".env", ".git/config", "secret.pem", "run.sh", "program.exe"],
)
def test_restricted_or_disallowed_files_are_blocked(
    editor_setup: tuple[ControlledEditor, Path], path: str
) -> None:
    editor, repository = editor_setup

    result = editor.apply_batch(repository, [create_edit(path, "blocked")])

    assert result.status == ToolStatus.BLOCKED
    assert not (repository / path).exists()


def test_oversized_content_is_blocked(
    editor_setup: tuple[ControlledEditor, Path],
) -> None:
    editor, repository = editor_setup

    result = editor.apply_batch(repository, [create_edit("large.txt", "x" * 257)])

    assert result.status == ToolStatus.BLOCKED

def test_task_allowed_paths_are_enforced_by_editor(
    editor_setup: tuple[ControlledEditor, Path],
) -> None:
    editor, repository = editor_setup

    accepted = editor.apply_batch(
        repository,
        [create_edit("architecture_plan.txt", "approved\n")],
        allowed_paths=["architecture_plan.txt"],
    )
    blocked = editor.apply_batch(
        repository,
        [create_edit("other.txt", "blocked\n")],
        allowed_paths=["architecture_plan.txt"],
        policy_context={"task_id": "TASK-001"},
    )

    assert accepted.status == ToolStatus.SUCCESS
    assert blocked.status == ToolStatus.BLOCKED
    assert blocked.error is not None
    assert blocked.error.code == "REPOSITORY_POLICY_VIOLATION"
    assert blocked.error.details["task_id"] == "TASK-001"
    assert not (repository / "other.txt").exists()
