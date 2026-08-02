from pydantic import BaseModel, ConfigDict


class ScenarioProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    profile_id: str
    scenario_type: str
    summary: str
    required_capabilities: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    path_policy_mode: str
    validation_rules: tuple[str, ...]


URL_SHORTENER_PROFILE = ScenarioProfile(
    profile_id="URL_SHORTENER_GREENFIELD",
    scenario_type="GREENFIELD",
    summary="A production-style local FastAPI URL-shortener target built by governed agents.",
    required_capabilities=(
        "create short URLs with optional aliases and expiration",
        "redirect active short codes",
        "report per-link analytics",
        "provide liveness and readiness endpoints",
        "manage schema exclusively through Alembic",
    ),
    allowed_paths=(
        "app/",
        "migrations/",
        "alembic/",
        "tests/",
        "scripts/",
        "alembic.ini",
        "pyproject.toml",
        "requirements.txt",
        ".env.example",
        ".gitignore",
        "README.md",
    ),
    path_policy_mode="SCENARIO_RESTRICTED",
    validation_rules=(
        "required HTTP routes and methods exist",
        "target application imports in an isolated subprocess",
        "target does not import control-plane modules",
        "target repository has no remote and no committed database files",
        "restricted secret and Git configuration files are absent",
        "Ruff, pytest, and the Alembic upgrade/downgrade cycle pass",
    ),
)
