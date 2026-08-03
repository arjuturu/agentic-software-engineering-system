# ruff: noqa: E501

from typing import Any


def requirement(requirement_text: str, *, brownfield: bool) -> dict[str, Any]:
    capabilities = [
        "Preserve URL creation, collision handling, and redirect behavior.",
        "Add click counting and a statistics endpoint.",
    ] if brownfield else [
        "Create persistent short URLs.",
        "Redirect existing short codes.",
        "Validate collisions, migrations, tests, and linting.",
    ]
    return {
        "normalized_requirement": requirement_text.strip(),
        "functional_requirements": capabilities,
        "non_functional_requirements": [
            "Use FastAPI, SQLAlchemy 2.x, SQLite, Alembic, Pytest, and Ruff.",
            "Remain deterministic and require no external services.",
        ],
        "assumptions": ["The workflow operates on a governed local repository."],
        "ambiguities": [],
        "clarification_questions": [],
        "acceptance_criteria": [
            "Required HTTP routes and persistence behavior pass acceptance tests.",
            "Alembic upgrade and downgrade pass from an empty SQLite database.",
            "The application imports, OpenAPI renders, Pytest passes, and Ruff passes.",
        ],
        "risks": ["Persistence migrations and redirect updates require regression coverage."],
        "material_ambiguity": False,
        "risk_level": "MEDIUM",
        "status": "READY_FOR_APPROVAL",
    }


def design(*, brownfield: bool) -> dict[str, Any]:
    return {
        "architecture_summary": (
            "Repository-aware analytics enhancement of the existing layered URL shortener."
            if brownfield
            else "Layered FastAPI URL shortener with Alembic-managed SQLite persistence."
        ),
        "components": [
            {
                "name": "API",
                "responsibility": "Create, redirect, and expose approved statistics routes.",
                "interfaces": ["FastAPI"],
                "dependencies": ["Service"],
            },
            {
                "name": "Service",
                "responsibility": "Coordinate validation, bounded allocation, and persistence.",
                "interfaces": ["Python functions"],
                "dependencies": ["Repository"],
            },
            {
                "name": "Repository",
                "responsibility": "Persist URL mappings through SQLAlchemy 2.x.",
                "interfaces": ["SQLAlchemy Session"],
                "dependencies": ["SQLite"],
            },
        ],
        "api_design": [
            {
                "name": "create URL",
                "method_or_type": "POST",
                "path_or_signature": "/api/v1/urls",
                "purpose": "Create a short URL.",
            },
            {
                "name": "redirect",
                "method_or_type": "GET",
                "path_or_signature": "/{short_code}",
                "purpose": "Redirect an existing code.",
            },
            *(
                [
                    {
                        "name": "statistics",
                        "method_or_type": "GET",
                        "path_or_signature": "/api/v1/urls/{short_code}/stats",
                        "purpose": "Return click analytics.",
                    }
                ]
                if brownfield
                else []
            ),
        ],
        "data_design": [
            {
                "entity": "UrlMapping",
                "purpose": "Store short-code mappings.",
                "fields": ["id", "original_url", "short_code"]
                + (["click_count"] if brownfield else []),
                "relationships": [],
                "constraints": ["short_code is unique"],
            }
        ],
        "control_flow": ["Validate input", "Persist mapping", "Resolve redirects"],
        "security_controls": ["Task-scoped paths", "Hash-guarded modifications"],
        "reliability_controls": ["Five-attempt collision bound", "Migration cycle"],
        "observability_controls": ["Deterministic validation and audit events"],
        "architecture_decisions": [
            {
                "decision": "Use synchronous SQLAlchemy 2.x sessions.",
                "rationale": "Matches the approved local workflow constraints.",
                "alternatives": ["Asynchronous persistence"],
                "consequences": ["Simple deterministic local execution"],
            }
        ],
        "risks": ["Migration compatibility must be validated."],
        "trade_offs": ["Local SQLite favors simplicity over distributed scale."],
        "limitations": ["No aliases, expiration, authentication, cache, UI, or cloud support."],
        "implementation_feasible": True,
        "status": "DESIGN_COMPLETE",
    }


def _task(
    task_id: str,
    title: str,
    task_type: str,
    dependencies: list[str],
    files: list[str],
    paths: list[str],
    commands: list[str],
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "title": title,
        "description": f"Execute {title.casefold()} using governed local tools.",
        "task_type": task_type,
        "dependencies": dependencies,
        "parallel_group": None,
        "risk_level": "MEDIUM" if task_type == "MIGRATION" else "LOW",
        "expected_files": files,
        "allowed_paths": paths,
        "entry_criteria": ["All declared dependencies are complete."],
        "exit_criteria": ["Owned outputs and validation commands pass."],
        "validation_commands": commands,
        "acceptance_criteria_covered": ["Approved URL-shortener behavior is implemented."],
    }


def greenfield_plan() -> dict[str, Any]:
    tasks = [
        _task(
            "TASK-001",
            "Set up dependencies and runnable project configuration",
            "SETUP",
            [],
            ["pyproject.toml", "requirements.txt", ".gitignore", "alembic.ini"],
            ["pyproject.toml", "requirements.txt", ".gitignore", "alembic.ini"],
            ["PYTHON_VERSION"],
        ),
        _task(
            "TASK-002",
            "Implement database models and initial migration",
            "MIGRATION",
            ["TASK-001"],
            [
                "app/__init__.py",
                "app/database.py",
                "app/models.py",
                "alembic/env.py",
                "alembic/script.py.mako",
                "alembic/versions/0001_create_url_mappings.py",
            ],
            ["app", "alembic"],
            ["TARGET_IMPORT_CHECK", "ALEMBIC_HISTORY"],
        ),
        _task(
            "TASK-003",
            "Implement schemas, repository, service, and short code generation",
            "IMPLEMENTATION",
            ["TASK-002"],
            [
                "app/schemas.py",
                "app/short_code_generator.py",
                "app/repository.py",
                "app/service.py",
            ],
            ["app"],
            ["TARGET_IMPORT_CHECK"],
        ),
        _task(
            "TASK-004",
            "Integrate FastAPI application entry point and routes",
            "INTEGRATION",
            ["TASK-003"],
            ["app/api/__init__.py", "app/api/routes.py", "app/main.py"],
            ["app"],
            ["TARGET_IMPORT_CHECK", "TARGET_OPENAPI_CHECK"],
        ),
        _task(
            "TASK-005",
            "Create acceptance testing coverage",
            "TESTING",
            ["TASK-004"],
            ["tests/conftest.py", "tests/test_api.py", "tests/test_service.py"],
            ["tests"],
            ["PYTEST"],
        ),
        _task(
            "TASK-006",
            "Create release documentation",
            "DOCUMENTATION",
            ["TASK-005"],
            [
                "README.md",
                "docs/validation.md",
                "docs/change-summary.md",
                "docs/pr-summary.md",
                "docs/known-limitations.md",
            ],
            ["README.md", "docs"],
            ["RUFF_CHECK"],
        ),
        _task(
            "TASK-007",
            "Run final validation",
            "VALIDATION",
            ["TASK-006"],
            [],
            [],
            [
                "TARGET_IMPORT_CHECK",
                "TARGET_OPENAPI_CHECK",
                "RUFF_CHECK",
                "PYTEST",
                "ALEMBIC_UPGRADE_HEAD",
                "ALEMBIC_DOWNGRADE_BASE",
                "ALEMBIC_UPGRADE_HEAD",
                "ALEMBIC_CURRENT",
            ],
        ),
    ]
    order = [task["task_id"] for task in tasks]
    return {
        "plan_summary": "Build and validate the approved URL-shortener application.",
        "tasks": tasks,
        "execution_order": order,
        "parallel_groups": [],
        "critical_path": order,
        "high_risk_tasks": ["TASK-002"],
        "assumptions": ["Architecture and approval gates remain outside executable tasks."],
        "implementation_risks": ["Collision and migration behavior require tests."],
        "status": "PLAN_COMPLETE",
    }


def brownfield_plan() -> dict[str, Any]:
    tasks = [
        _task("TASK-001", "Verify repository baseline", "SETUP", [], [], ["README.md"], ["TARGET_IMPORT_CHECK", "TARGET_OPENAPI_CHECK"]),
        _task("TASK-002", "Add analytics model field", "IMPLEMENTATION", ["TASK-001"], ["app/models.py"], ["app/models.py"], ["TARGET_IMPORT_CHECK"]),
        _task("TASK-003", "Create analytics migration", "MIGRATION", ["TASK-002"], ["alembic/versions/0002_add_click_count.py"], ["alembic/versions"], ["ALEMBIC_HISTORY"]),
        _task("TASK-004", "Enhance repository and service redirect behavior", "IMPLEMENTATION", ["TASK-003"], ["app/repository.py", "app/service.py"], ["app/repository.py", "app/service.py"], ["TARGET_IMPORT_CHECK"]),
        _task("TASK-005", "Integrate statistics API endpoint", "INTEGRATION", ["TASK-004"], ["app/schemas.py", "app/api/routes.py"], ["app/schemas.py", "app/api/routes.py"], ["TARGET_IMPORT_CHECK", "TARGET_OPENAPI_CHECK"]),
        _task("TASK-006", "Add analytics regression testing", "TESTING", ["TASK-005"], ["tests/test_api.py"], ["tests/test_api.py"], ["PYTEST"]),
        _task("TASK-007", "Update release documentation", "DOCUMENTATION", ["TASK-006"], ["README.md", "docs/change-summary.md", "docs/known-limitations.md"], ["README.md", "docs"], ["RUFF_CHECK"]),
        _task("TASK-008", "Run final validation", "VALIDATION", ["TASK-007"], [], [], ["TARGET_IMPORT_CHECK", "TARGET_OPENAPI_CHECK", "RUFF_CHECK", "PYTEST", "ALEMBIC_UPGRADE_HEAD", "ALEMBIC_DOWNGRADE_BASE", "ALEMBIC_UPGRADE_HEAD", "ALEMBIC_CURRENT"]),
    ]
    order = [task["task_id"] for task in tasks]
    return {
        "plan_summary": "Apply a repository-aware click analytics enhancement.",
        "tasks": tasks,
        "execution_order": order,
        "parallel_groups": [],
        "critical_path": order,
        "high_risk_tasks": ["TASK-003"],
        "assumptions": ["The copied Greenfield baseline is immutable at its source."],
        "implementation_risks": ["Existing redirect behavior must remain compatible."],
        "status": "PLAN_COMPLETE",
    }


GREEN_FILES = {
    "pyproject.toml": """[project]
name = "scripted-url-shortener"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["fastapi", "sqlalchemy", "alembic", "pydantic"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
ignore = ["E501"]

[tool.ruff.lint.per-file-ignores]
"app/api/*.py" = ["B008"]
""",
    "requirements.txt": "fastapi\nsqlalchemy\nalembic\npydantic\npytest\nhttpx\nruff\n",
    ".gitignore": ".venv/\n__pycache__/\n*.pyc\n.pytest_cache/\n.ruff_cache/\n*.db\n",
    "alembic.ini": "[alembic]\nscript_location = alembic\nsqlalchemy.url = sqlite:///./url_shortener.db\n",
    "app/__init__.py": "",
    "app/database.py": """from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = "sqlite:///./url_shortener.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
""",
    "app/models.py": """from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UrlMapping(Base):
    __tablename__ = "url_mappings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    original_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    short_code: Mapped[str] = mapped_column(String(8), nullable=False, unique=True, index=True)
""",
    "alembic/env.py": """from sqlalchemy import engine_from_config, pool

from alembic import context
from app import models  # noqa: F401
from app.database import Base

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
""",
    "alembic/script.py.mako": """\"\"\"${message}\"\"\"
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

def upgrade() -> None:
    ${upgrades if upgrades else "pass"}

def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
""",
    "alembic/versions/0001_create_url_mappings.py": """import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("url_mappings", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("original_url", sa.String(2048), nullable=False), sa.Column("short_code", sa.String(8), nullable=False), sa.UniqueConstraint("short_code", name="uq_url_mappings_short_code"))
    op.create_index("ix_url_mappings_short_code", "url_mappings", ["short_code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_url_mappings_short_code", table_name="url_mappings")
    op.drop_table("url_mappings")
""",
    "app/schemas.py": """from urllib.parse import urlsplit

from pydantic import BaseModel, field_validator


class UrlCreate(BaseModel):
    original_url: str

    @field_validator("original_url", mode="before")
    @classmethod
    def validate_url(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("original_url must be a non-empty HTTP or HTTPS URL")
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("original_url must be an absolute HTTP or HTTPS URL")
        return normalized


class UrlResponse(BaseModel):
    original_url: str
    short_code: str
    short_url: str
""",
    "app/short_code_generator.py": """import secrets
import string

ALPHABET = string.ascii_letters + string.digits


def generate_short_code(length: int = 8) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))
""",
    "app/repository.py": """from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UrlMapping


def find_by_code(session: Session, short_code: str) -> UrlMapping | None:
    return session.scalar(select(UrlMapping).where(UrlMapping.short_code == short_code))


def create_mapping(session: Session, original_url: str, short_code: str) -> UrlMapping:
    item = UrlMapping(original_url=original_url, short_code=short_code)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item
""",
    "app/service.py": """from collections.abc import Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import repository
from app.models import UrlMapping
from app.short_code_generator import generate_short_code


class CollisionExhaustedError(Exception):
    pass


def create_short_url(session: Session, original_url: str, code_factory: Callable[[], str] = generate_short_code) -> UrlMapping:
    for _ in range(5):
        code = code_factory()
        if repository.find_by_code(session, code) is not None:
            continue
        try:
            return repository.create_mapping(session, original_url, code)
        except IntegrityError:
            session.rollback()
    raise CollisionExhaustedError
""",
    "app/api/__init__.py": "",
    "app/api/routes.py": """from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import repository
from app.database import get_db
from app.schemas import UrlCreate, UrlResponse
from app.service import CollisionExhaustedError, create_short_url

router = APIRouter()


@router.post("/api/v1/urls", response_model=UrlResponse, status_code=201)
def create_url(payload: UrlCreate, request: Request, session: Session = Depends(get_db)) -> UrlResponse:
    try:
        item = create_short_url(session, payload.original_url)
    except CollisionExhaustedError as exc:
        raise HTTPException(status_code=503, detail="Unable to generate a unique short code") from exc
    base = str(request.base_url).rstrip("/")
    return UrlResponse(original_url=item.original_url, short_code=item.short_code, short_url=f"{base}/{item.short_code}")


@router.get("/{short_code}")
def redirect(short_code: str, session: Session = Depends(get_db)) -> RedirectResponse:
    item = repository.find_by_code(session, short_code)
    if item is None:
        raise HTTPException(status_code=404, detail="Short URL not found")
    return RedirectResponse(item.original_url, status_code=307)
""",
    "app/main.py": """from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(title="URL Shortener")
app.include_router(router)
""",
    "tests/conftest.py": """import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
""",
    "tests/test_api.py": """def test_create_and_redirect(client):
    created = client.post("/api/v1/urls", json={"original_url": "  https://example.com/path  "})
    assert created.status_code == 201
    body = created.json()
    assert body["original_url"] == "https://example.com/path"
    assert len(body["short_code"]) == 8
    redirected = client.get(f"/{body['short_code']}", follow_redirects=False)
    assert redirected.status_code == 307
    assert redirected.headers["location"] == "https://example.com/path"


def test_invalid_and_missing_urls(client):
    assert client.post("/api/v1/urls", json={"original_url": "not-a-url"}).status_code == 422
    missing = client.get("/UNKNOWN", follow_redirects=False)
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Short URL not found"}
""",
    "tests/test_service.py": """import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.service import CollisionExhaustedError, create_short_url


def test_generated_codes_are_unique(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'unique.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        first = create_short_url(session, "https://example.com/one")
        second = create_short_url(session, "https://example.com/two")
    assert first.short_code != second.short_code
    assert len(first.short_code) == len(second.short_code) == 8


def test_collision_retry_is_bounded(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'collision.db'}")
    Base.metadata.create_all(engine)
    attempts = 0

    def collision() -> str:
        nonlocal attempts
        attempts += 1
        return "COLLIDE1"

    with Session(engine, expire_on_commit=False) as session:
        create_short_url(session, "https://example.com/original", collision)
        attempts = 0
        with pytest.raises(CollisionExhaustedError):
            create_short_url(session, "https://example.com/duplicate", collision)
    assert attempts == 5
""",
    "docs/validation.md": "# Validation\n\nPytest, Ruff, import, OpenAPI, and Alembic checks are required.\n",
    "docs/change-summary.md": "# Change Summary\n\nImplemented URL creation and redirection.\n",
    "docs/pr-summary.md": "# PR Summary\n\nLocal governed change; no remote PR was created.\n",
    "docs/known-limitations.md": "# Known Limitations\n\nNo aliases, expiration, authentication, analytics, UI, or cloud deployment.\n",
}


BROWN_REPLACEMENTS = {
    "app/models.py": GREEN_FILES["app/models.py"].replace(
        "from sqlalchemy import String", "from sqlalchemy import Integer, String"
    ).replace(
        "    short_code: Mapped[str] = mapped_column(String(8), nullable=False, unique=True, index=True)\n",
        "    short_code: Mapped[str] = mapped_column(String(8), nullable=False, unique=True, index=True)\n    click_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)\n",
    ),
    "app/repository.py": GREEN_FILES["app/repository.py"] + """

def increment_click_count(session: Session, item: UrlMapping) -> UrlMapping:
    item.click_count += 1
    session.commit()
    session.refresh(item)
    return item
""",
    "app/service.py": GREEN_FILES["app/service.py"] + """

def resolve_and_count(session: Session, short_code: str) -> UrlMapping | None:
    item = repository.find_by_code(session, short_code)
    return repository.increment_click_count(session, item) if item is not None else None
""",
    "app/schemas.py": GREEN_FILES["app/schemas.py"] + """

class UrlStatsResponse(UrlResponse):
    click_count: int
""",
    "app/api/routes.py": """from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import repository
from app.database import get_db
from app.schemas import UrlCreate, UrlResponse, UrlStatsResponse
from app.service import CollisionExhaustedError, create_short_url, resolve_and_count

router = APIRouter()


def _response(item, request: Request) -> dict:
    base = str(request.base_url).rstrip("/")
    return {"original_url": item.original_url, "short_code": item.short_code, "short_url": f"{base}/{item.short_code}"}


@router.post("/api/v1/urls", response_model=UrlResponse, status_code=201)
def create_url(payload: UrlCreate, request: Request, session: Session = Depends(get_db)):
    try:
        item = create_short_url(session, payload.original_url)
    except CollisionExhaustedError as exc:
        raise HTTPException(status_code=503, detail="Unable to generate a unique short code") from exc
    return _response(item, request)


@router.get("/api/v1/urls/{short_code}/stats", response_model=UrlStatsResponse)
def stats(short_code: str, request: Request, session: Session = Depends(get_db)):
    item = repository.find_by_code(session, short_code)
    if item is None:
        raise HTTPException(status_code=404, detail="Short URL not found")
    return {**_response(item, request), "click_count": item.click_count}


@router.get("/{short_code}")
def redirect(short_code: str, session: Session = Depends(get_db)) -> RedirectResponse:
    item = resolve_and_count(session, short_code)
    if item is None:
        raise HTTPException(status_code=404, detail="Short URL not found")
    return RedirectResponse(item.original_url, status_code=307)
""",
    "tests/test_api.py": GREEN_FILES["tests/test_api.py"] + """

def test_click_count_and_stats(client):
    created = client.post("/api/v1/urls", json={"original_url": "https://example.org"}).json()
    code = created["short_code"]
    initial = client.get(f"/api/v1/urls/{code}/stats")
    assert initial.status_code == 200
    assert initial.json()["click_count"] == 0
    assert client.get(f"/{code}", follow_redirects=False).status_code == 307
    updated = client.get(f"/api/v1/urls/{code}/stats")
    assert updated.json()["click_count"] == 1
""",
}


ANALYTICS_MIGRATION = """import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("url_mappings") as batch:
        batch.add_column(sa.Column("click_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("url_mappings") as batch:
        batch.drop_column("click_count")
"""


def _create(path: str, content: str) -> dict[str, Any]:
    return {
        "operation": "CREATE",
        "relative_path": path,
        "content": content,
        "expected_absent": True,
        "expected_hash": None,
        "old_text": None,
        "replacement_text": None,
    }


def _modify(path: str, content: str, hashes: dict[str, str]) -> dict[str, Any]:
    return {
        "operation": "MODIFY",
        "relative_path": path,
        "content": content,
        "expected_absent": False,
        "expected_hash": hashes.get(path),
        "old_text": None,
        "replacement_text": None,
    }


def coding(payload: dict[str, Any], *, brownfield: bool) -> dict[str, Any]:
    task_id = payload.get("active_task", {}).get("task_id", "")
    hashes = payload.get("file_hashes", {})
    edits: list[dict[str, Any]] = []
    if not brownfield:
        task_files = {
            "TASK-001": ["pyproject.toml", "requirements.txt", ".gitignore", "alembic.ini"],
            "TASK-002": ["app/__init__.py", "app/database.py", "app/models.py", "alembic/env.py", "alembic/script.py.mako", "alembic/versions/0001_create_url_mappings.py"],
            "TASK-003": ["app/schemas.py", "app/short_code_generator.py", "app/repository.py", "app/service.py"],
            "TASK-004": ["app/api/__init__.py", "app/api/routes.py", "app/main.py"],
            "TASK-005": ["tests/conftest.py", "tests/test_api.py", "tests/test_service.py"],
            "TASK-006": ["README.md", "docs/validation.md", "docs/change-summary.md", "docs/pr-summary.md", "docs/known-limitations.md"],
            "TASK-007": [],
        }
        for path in task_files.get(task_id, []):
            content = (
                "# Scripted URL Shortener\n\nRun Alembic, Uvicorn, Pytest, and Ruff locally.\n"
                if path == "README.md"
                else GREEN_FILES[path]
            )
            edits.append(_modify(path, content, hashes) if path in hashes else _create(path, content))
    else:
        if task_id == "TASK-002":
            edits = [_modify("app/models.py", BROWN_REPLACEMENTS["app/models.py"], hashes)]
        elif task_id == "TASK-003":
            edits = [_create("alembic/versions/0002_add_click_count.py", ANALYTICS_MIGRATION)]
        elif task_id == "TASK-004":
            edits = [
                _modify(path, BROWN_REPLACEMENTS[path], hashes)
                for path in ("app/repository.py", "app/service.py")
            ]
        elif task_id == "TASK-005":
            edits = [
                _modify(path, BROWN_REPLACEMENTS[path], hashes)
                for path in ("app/schemas.py", "app/api/routes.py")
            ]
        elif task_id == "TASK-006":
            edits = [_modify("tests/test_api.py", BROWN_REPLACEMENTS["tests/test_api.py"], hashes)]
        elif task_id == "TASK-007":
            edits = [
                _modify(
                    "README.md",
                    "# Scripted URL Shortener\n\nIncludes click analytics and a stats endpoint.\n",
                    hashes,
                ),
                _modify(
                    "docs/change-summary.md",
                    "# Change Summary\n\nAdded click counting and statistics.\n",
                    hashes,
                ),
                _modify(
                    "docs/known-limitations.md",
                    "# Known Limitations\n\nNo aliases, expiration, authentication, cache, UI, or cloud.\n",
                    hashes,
                ),
            ]
    return {
        "implementation_summary": "Apply the deterministic task-scoped URL-shortener change.",
        "change_plan": [{"task_id": task_id, "paths": [edit["relative_path"] for edit in edits]}],
        "structured_edits": edits,
        "tests_created_or_modified": [edit["relative_path"] for edit in edits if edit["relative_path"].startswith("tests/")],
        "migrations_created": [edit["relative_path"] for edit in edits if "versions/" in edit["relative_path"]],
        "assumptions": ["Current repository hashes were supplied by the controlled context."],
        "risks": [],
        "dependency_changes": [],
        "high_risk_change": False,
        "high_risk_reason": None,
        "status": "READY_TO_APPLY",
        "replan_reason": None,
    }
