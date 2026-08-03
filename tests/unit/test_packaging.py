import tomllib
from pathlib import Path

RUNTIME_DEPENDENCIES = {
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "alembic",
    "pydantic",
    "pydantic-settings",
    "python-dotenv",
    "langgraph",
    "langgraph-checkpoint-sqlite",
    "langchain-core",
    "langchain-openai",
}


def _dependency_name(requirement: str) -> str:
    return requirement.split("[", 1)[0].split(">", 1)[0].split("=", 1)[0].strip().casefold()


def test_runtime_dependencies_are_consistent_between_manifests() -> None:
    root = Path(__file__).resolve().parents[2]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    pyproject_names = {
        _dependency_name(item) for item in project["project"]["dependencies"]
    }
    requirement_names = {
        _dependency_name(item)
        for item in (root / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if item.strip() and not item.lstrip().startswith("#")
    }

    assert RUNTIME_DEPENDENCIES <= pyproject_names
    assert RUNTIME_DEPENDENCIES <= requirement_names


def test_gitignore_covers_runtime_and_secret_outputs() -> None:
    root = Path(__file__).resolve().parents[2]
    patterns = set((root / ".gitignore").read_text(encoding="utf-8").splitlines())

    assert {
        ".env",
        ".venv/",
        "**/__pycache__/",
        "*.py[cod]",
        ".pytest_cache/",
        ".ruff_cache/",
        "data/*.db",
        "data/*checkpoint*",
        "workspace/*",
        "logs/",
        "generated_artifacts/*",
    } <= patterns
