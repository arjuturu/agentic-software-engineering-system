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

## Phase 2: controlled engineering tools

The Agentic Software Engineering System remains the **control plane**. Future generated
applications are separate **target applications** and may only be manipulated beneath
the workspace directory; the intended greenfield target is
workspace/url-shortener-greenfield/. Phase 2 does not generate that application.

The controlled tool layer provides canonical path enforcement, workspace management,
read-only repository scanning, exact hash-guarded edits, local Git operations, approved
command execution, test and migration runners, and workflow artifact storage.

### Safety model

- Canonical resolved paths must remain beneath the configured workspace or artifact root.
  Traversal, external absolute paths, escaping links/junctions, .env, .git/config,
  credentials, private keys, and system/device paths are blocked.
- File edits support only CREATE and exact MODIFY. Every batch is fully validated before
  writing, uses atomic replacement, and restores earlier writes if a later write fails.
- Commands are selected by fixed IDs. They use argument arrays, shell=False, timeouts,
  bounded output, and a minimal sanitized child environment. Arbitrary command strings,
  pipes, redirects, and unrestricted revisions are not accepted.
- Git operations are local-only and workspace-bound. The tool can initialize, inspect,
  branch, stage explicit existing files, commit, diff, and restore tracked files. It
  disables hooks, signing, and external diff helpers, and cannot add remotes, clone,
  fetch, pull, push, merge, force-push, or clean ignored files.
- Repository scanning never imports or executes target code, does not read restricted or
  binary files, bounds file sizes/counts, and does not follow escaping symbolic links.

### Phase 2 verification

~~~powershell
python -m ruff check .
python -m pytest -v
python -m pytest tests/integration/test_greenfield_tool_flow.py -v
~~~

All Phase 2 integration tests use temporary workspace, artifact, Git, database, and
migration directories. They do not modify the control plane's real workspace, data, or
generated_artifacts contents.
## Current limitations

Phase 2 provides deterministic tools but no workflow execution or autonomous behavior.
Agents and LangGraph orchestration begin in Phase 3. Gradio, OpenAI integration,
URL-shortener business APIs, API scanning,
remote Git workflows and deployment will be implemented in later phases.
