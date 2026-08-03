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
    summary=(
        "A governed greenfield URL-shortener target whose functional scope comes only from the "
        "user requirement and approved clarifications."
    ),
    required_capabilities=(),
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
        "docs/",
    ),
    path_policy_mode="SCENARIO_RESTRICTED",
    validation_rules=(
        "HTTP routes and methods explicitly required by the approved requirement exist",
        "target application imports in an isolated subprocess",
        "target does not import control-plane modules",
        "target repository has no remote and no committed database files",
        "restricted secret and Git configuration files are absent",
        "approved quality and migration requirements are validated deterministically",
    ),
)


URL_SHORTENER_BROWNFIELD_PROFILE = ScenarioProfile(
    profile_id="URL_SHORTENER_BROWNFIELD",
    scenario_type="BROWNFIELD",
    summary=(
        "Enhance an existing governed URL-shortener repository using repository-aware "
        "analysis and controlled modifications."
    ),
    required_capabilities=(),
    allowed_paths=(
        "app/",
        "alembic/",
        "migrations/",
        "tests/",
        "docs/",
        "README.md",
        "pyproject.toml",
        "requirements.txt",
        "alembic.ini",
        ".env.example",
        ".gitignore",
    ),
    path_policy_mode="SCENARIO_RESTRICTED",
    validation_rules=(
        "existing URL creation and redirect behavior remains valid",
        "approved Brownfield APIs and schema changes exist",
        "new Alembic migration upgrades and downgrades successfully",
        "target application imports in an isolated subprocess",
        "target does not import control-plane modules",
        "target repository has no remote and no committed database files",
        "restricted secret and Git configuration files are absent",
        "regression tests and approved quality checks pass",
    ),
)
