import hashlib
from pathlib import Path

from app.config import Settings
from app.orchestration.nodes import WorkflowNodes
from app.tools.controlled_editor import ControlledEditor
from app.tools.models import EditOperation, StructuredEdit, ToolStatus
from app.tools.path_policy import PathPolicy


def _editor(tmp_path: Path) -> tuple[ControlledEditor, Path]:
    workspace_root = tmp_path / "workspace"
    artifact_root = tmp_path / "artifacts"
    repository = workspace_root / "target"
    repository.mkdir(parents=True)
    artifact_root.mkdir()
    settings = Settings(
        _env_file=None,
        WORKSPACE_ROOT=workspace_root,
        ARTIFACT_ROOT=artifact_root,
        MAX_EDIT_FILE_BYTES=4096,
    )
    return ControlledEditor(PathPolicy(settings, project_root=tmp_path), settings), repository


def _node(editor: ControlledEditor) -> WorkflowNodes:
    node = object.__new__(WorkflowNodes)
    node.editor = editor
    return node


def test_first_attempt_context_is_exact_allowlisted_and_supports_modify_create(
    tmp_path: Path,
) -> None:
    editor, repository = _editor(tmp_path)
    readme = repository / "README.md"
    readme.write_bytes(b"baseline documentation\n")
    (repository / "unrelated.txt").write_bytes(b"private unrelated context\n")
    active_task = {
        "task_id": "TASK-007",
        "task_type": "DOCUMENTATION",
        "expected_files": ["README.md", "new-release.md"],
        "allowed_paths": ["README.md", "new-release.md"],
    }
    state = {
        "scenario_profile": {"allowed_paths": [], "path_policy_mode": "TASK_SCOPED"},
        "changed_files": ["unrelated.txt"],
        "retry_context": {},
    }

    context = _node(editor)._coding_repository_context(state, repository, active_task)

    assert context == [
        {
            "relative_path": "README.md",
            "sha256": hashlib.sha256(b"baseline documentation\n").hexdigest(),
            "content": "baseline documentation\n",
        }
    ]
    modify = editor.apply_batch(
        repository,
        [
            StructuredEdit(
                operation=EditOperation.MODIFY,
                relative_path="README.md",
                expected_hash=context[0]["sha256"],
                content="updated documentation\n",
            )
        ],
        allowed_paths=active_task["allowed_paths"],
    )
    create = editor.apply_batch(
        repository,
        [
            StructuredEdit(
                operation=EditOperation.CREATE,
                relative_path="new-release.md",
                content="release notes\n",
                expected_absent=True,
            )
        ],
        allowed_paths=active_task["allowed_paths"],
    )
    assert modify.status == ToolStatus.SUCCESS
    assert create.status == ToolStatus.SUCCESS


def test_retry_context_refreshes_hash_and_still_excludes_unrelated_files(
    tmp_path: Path,
) -> None:
    editor, repository = _editor(tmp_path)
    readme = repository / "README.md"
    readme.write_bytes(b"first version\n")
    (repository / "outside.py").write_bytes(b"secret = False\n")
    task = {
        "task_id": "TASK-007",
        "task_type": "DOCUMENTATION",
        "expected_files": ["README.md"],
        "allowed_paths": ["README.md"],
    }
    first = _node(editor)._coding_repository_context(
        {
            "scenario_profile": {"allowed_paths": [], "path_policy_mode": "TASK_SCOPED"},
            "retry_context": {},
        },
        repository,
        task,
    )
    readme.write_bytes(b"second version\n")
    retry = _node(editor)._coding_repository_context(
        {
            "scenario_profile": {"allowed_paths": [], "path_policy_mode": "TASK_SCOPED"},
            "retry_context": {"active": True},
            "code_change_plan": {
                "structured_edits": [
                    {"relative_path": "README.md"},
                    {"relative_path": "outside.py"},
                ]
            },
            "changed_files": ["outside.py"],
        },
        repository,
        task,
    )

    assert first[0]["sha256"] != retry[0]["sha256"]
    assert retry == [
        {
            "relative_path": "README.md",
            "sha256": hashlib.sha256(b"second version\n").hexdigest(),
            "content": "second version\n",
        }
    ]
