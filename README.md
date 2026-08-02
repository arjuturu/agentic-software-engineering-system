# Agentic Software Engineering System

A governed, local foundation for agentic software-delivery automation. Phase 1 establishes
the web application, configuration, logging, persistence, migrations, health checks, and
test infrastructure on which later phases can build.

## Phase 1 scope

This phase provides a synchronous FastAPI application, Pydantic settings, structured
standard-library logging, SQLAlchemy 2.x typed models, SQLite, a deterministic Alembic
migration for ten application tables, operational health endpoints, local scripts, and
unit/integration tests.

LangGraph orchestration, agents, Gradio, OpenAI integration, URL-shortener business
functionality, API scanning, Git automation, and deployment are intentionally deferred
to later phases.

## Prerequisites

- Python 3.11 or newer
- Git available on PATH
- A terminal capable of creating a Python virtual environment

## Windows PowerShell setup

~~~powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python scripts/init_local.py
alembic upgrade head
python -m uvicorn app.main:app --reload
~~~

## macOS and Linux setup

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python scripts/init_local.py
alembic upgrade head
python -m uvicorn app.main:app --reload
~~~

The API runs at http://127.0.0.1:8000. Interactive Swagger documentation is available
at http://127.0.0.1:8000/docs.

## Environment configuration

Copy .env.example to .env and adjust local values as needed. Never commit .env.
Defaults use repository-local data, workspace, and generated_artifacts directories.
No OpenAI key is needed in Phase 1. Paths are resolved using pathlib, and importing
settings does not create directories.

## Database migrations

Alembic exclusively manages schema changes; application startup never calls
Base.metadata.create_all().

~~~bash
alembic upgrade head
alembic current
alembic downgrade base
alembic upgrade head
~~~

To initialize directories and migrate in one step:

~~~bash
python scripts/init_local.py --migrate
~~~

## Verification and quality checks

Windows PowerShell:

~~~powershell
python scripts/verify_environment.py
python -m pytest
python -m ruff check .
~~~

The same commands work in macOS/Linux shells after activating the virtual environment.
For coverage, run python -m pytest --cov=app --cov-report=term-missing.

## Health endpoints

~~~text
GET /health/live
{"status":"UP"}

GET /health/ready
{"status":"UP","database":"UP","artifactStorage":"UP","workspace":"UP","git":"UP","workflowEngine":"UP"}
~~~

Readiness checks SQLite connectivity, artifact/workspace storage, the Git executable,
and the configured checkpoint database parent directory. A mandatory failure returns
HTTP 503 with the failed component marked DOWN; responses do not expose local paths,
credentials, or exception traces.

## Current limitations

Phase 1 contains storage models for future workflows but no workflow execution behavior.
LangGraph, agents, Gradio, OpenAI integration, URL-shortener business APIs, API scanning,
Git-writing workflows, and deployment will be implemented in later phases.
