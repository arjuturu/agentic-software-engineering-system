import os
from pathlib import Path

import pytest

from app.config import Settings
from app.tools.models import ToolStatus
from app.tools.path_policy import PathPolicy, PathPolicyError
from app.tools.repository_scanner import RepositoryScanner


@pytest.fixture
def scanner_setup(tmp_path: Path) -> tuple[RepositoryScanner, Path]:
    workspace_root = tmp_path / "workspace"
    artifact_root = tmp_path / "artifacts"
    repository = workspace_root / "project"
    repository.mkdir(parents=True)
    artifact_root.mkdir()
    settings = Settings(
        _env_file=None,
        WORKSPACE_ROOT=workspace_root,
        ARTIFACT_ROOT=artifact_root,
        MAX_SCAN_FILES=50,
        MAX_SCAN_FILE_BYTES=128,
    )
    return RepositoryScanner(PathPolicy(settings, project_root=tmp_path), settings), repository


def test_detects_python_project_files(scanner_setup: tuple[RepositoryScanner, Path]) -> None:
    scanner, repository = scanner_setup
    (repository / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (repository / "app").mkdir()
    (repository / "app/__init__.py").write_text("", encoding="utf-8")
    (repository / "app/main.py").write_text(
        "from fastapi import FastAPI\nfrom sqlalchemy import select\n", encoding="utf-8"
    )
    (repository / "tests").mkdir()
    (repository / "tests/test_app.py").write_text("def test_ok(): pass\n", encoding="utf-8")
    (repository / "migrations/versions").mkdir(parents=True)
    (repository / "migrations/versions/001.py").write_text("revision='001'\n", encoding="utf-8")

    result = scanner.scan(repository)

    assert result.status == ToolStatus.SUCCESS
    assert result.file_count == 5
    assert "pyproject.toml" in result.detected_project_files
    assert "app" in result.detected_python_packages
    assert "tests/test_app.py" in result.detected_test_files
    assert "migrations/versions/001.py" in result.detected_migration_files
    assert "app/main.py" in result.fastapi_files
    assert "app/main.py" in result.sqlalchemy_files


def test_skips_binary_restricted_and_large_files(
    scanner_setup: tuple[RepositoryScanner, Path],
) -> None:
    scanner, repository = scanner_setup
    (repository / "safe.txt").write_text("safe", encoding="utf-8")
    (repository / "binary.dat").write_bytes(b"abc\x00def")
    (repository / ".env").write_text("PASSWORD=private", encoding="utf-8")
    (repository / "large.txt").write_text("x" * 129, encoding="utf-8")

    result = scanner.scan(repository)

    assert result.status == ToolStatus.PARTIAL
    assert ".env" in result.restricted_files_found
    assert {"binary.dat", ".env", "large.txt"}.issubset(result.skipped_files)
    assert scanner.read_safe_text_file(repository, "safe.txt") == "safe"
    with pytest.raises(PathPolicyError):
        scanner.read_safe_text_file(repository, ".env")


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symbolic links are unsupported")
def test_does_not_follow_unsafe_links(
    scanner_setup: tuple[RepositoryScanner, Path], tmp_path: Path
) -> None:
    scanner, repository = scanner_setup
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")
    link = repository / "linked.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symbolic link creation is not permitted on this host")

    result = scanner.scan(repository)

    assert "linked.txt" in result.skipped_files
    assert "linked.txt" not in scanner.list_files(repository)


def test_enforces_file_count_limit(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    repository = workspace / "project"
    repository.mkdir(parents=True)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    for number in range(3):
        (repository / f"{number}.txt").write_text("x", encoding="utf-8")
    settings = Settings(
        _env_file=None,
        WORKSPACE_ROOT=workspace,
        ARTIFACT_ROOT=artifacts,
        MAX_SCAN_FILES=2,
    )
    scanner = RepositoryScanner(PathPolicy(settings, project_root=tmp_path), settings)

    result = scanner.scan(repository)

    assert result.status == ToolStatus.PARTIAL
    assert result.file_count == 2
    assert "<file-limit-reached>" in result.skipped_files
