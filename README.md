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

## Phase 3: stateful workflow and human governance

Phase 3 coordinates Requirement, Design, Planning, Repository/Coding, Validation, and
Documentation/Release agents through a deterministic LangGraph `StateGraph`. Agents
produce bounded Pydantic outputs; they do not route the workflow, approve their own
work, or receive raw filesystem or shell access. Phase 2 path, edit, command, and
local-only Git policies remain the enforcement boundary.

The control plane is this application. Generated targets are independent local Git repositories
beneath `workspace/`. The control-plane repository does not itself implement URL-shortener business
APIs. Phase 4 specializes the governed greenfield workflow so agents can create that functionality
inside an independent target workspace.

### Provider modes and checkpointing

`LLM_MODE=SCRIPTED` is the default and is deterministic, offline, and suitable for all
tests. `LLM_MODE=OPENAI` uses structured `ChatOpenAI` output and requires both
`OPENAI_API_KEY` in the uncommitted `.env`. The default model is `gpt-5.6-terra`, with explicit
`OPENAI_REASONING_EFFORT=medium`; both values can be overridden. Startup fails safely when the
key or model is missing. Keys are never placed in graph state or artifacts.

Application metadata remains in `data/application.db`. Durable LangGraph checkpoints
use the separate `data/langgraph_checkpoints.db`. The synchronous SQLite connection is
owned by the FastAPI lifespan and closed at shutdown. Clarification, requirement,
architecture/plan, and release decisions pause with `interrupt()` and resume with the
same thread ID using `Command(resume=...)`.

Failure handling includes bounded coding retries, requirement/design/plan replanning,
baseline-commit rollback, and terminal safe stop for policy or security violations.
Validation and preliminary documentation execute as parallel graph branches and join
before the release recommendation.

Planning output uses the canonical task types `SETUP`, `IMPLEMENTATION`, `INTEGRATION`,
`MIGRATION`, `TESTING`, `DOCUMENTATION`, and `VALIDATION`. Fixable structural plan failures are
returned to the Planning Agent with exact validation evidence for up to two corrections; only a
validated plan is persisted as executable workflow tasks. Coding attempts receive current content
and SHA-256 hashes only for existing files permitted by the active task.

### Run and verify Phase 3

~~~powershell
python -m pip install -r requirements.txt
alembic upgrade head
python -m uvicorn app.main:app --reload
python -m ruff check .
python -m pytest -q
python -m pytest tests/integration/test_phase3_end_to_end.py -v
~~~

Swagger is available at `http://127.0.0.1:8000/docs` and includes workflow, approval,
artifact, and audit APIs.

### Scripted workflow example

~~~powershell
$workflow = Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/v1/workflows' -ContentType 'application/json' -Body (@{
  scenarioType = 'GREENFIELD'
  requirement = 'Create a small Python service with tests.'
  workspaceName = 'sample-greenfield'
  scriptedScenario = 'HAPPY_PATH'
} | ConvertTo-Json)

$approval = $workflow.pendingApproval
$workflow = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/workflows/$($workflow.workflowId)/approvals/$($approval.approvalId)" -ContentType 'application/json' -Body (@{
  gateType = $approval.gateType
  stateVersion = $approval.stateVersion
  action = 'APPROVE'
  comments = 'Proceed'
  conditions = @()
  decidedBy = 'local-user'
} | ConvertTo-Json)
~~~

Repeat the approval request for the combined architecture/plan gate and the release
gate. Clarification workflows resume through
`POST /api/v1/workflows/{workflow_id}/clarifications`. Inspect progress and evidence at:

~~~text
GET /api/v1/workflows/{workflow_id}
GET /api/v1/workflows/{workflow_id}/artifacts
GET /api/v1/workflows/{workflow_id}/artifacts/{file_name}
GET /api/v1/workflows/{workflow_id}/audit
~~~

### Phase 3 limitations

The OpenAI provider has no web, file-search, code-interpreter, or arbitrary tool access.
All Git work remains local; there are no remotes, pull requests, deployment flows, or
Gradio UI. The generated project is intentionally a tiny generic Python fixture, not a
production application or URL shortener.
## Phase 4 — Stateful URL-shortener specialization

Phase 4 adds a focused `URL_SHORTENER_GREENFIELD` scenario profile without changing the six-agent
LangGraph topology. The deterministic resolver requires a greenfield request plus strong
URL-shortening and supporting capability evidence; weak keyword matches remain `GENERIC`. The
resolved, JSON-serializable profile is stored in workflow state and supplied to every agent.

The profile contains constraints and validation rules only. It does not contain target source
bodies, a hidden implementation template, or a forced exact package tree. A generated target must
remain an independent local repository beneath `workspace/`, must not import control-plane modules,
must not configure a remote, and must not commit SQLite database files.

Deterministic target validation checks the required HTTP methods and routes from isolated OpenAPI
evidence, target importability, control-plane independence, restricted files, Git remotes, tracked
database files, Alembic configuration and the upgrade/downgrade/re-upgrade cycle, Ruff, and pytest.
Agent prose cannot override failed deterministic evidence.

The user requirement and approved clarifications are the sole product-scope authority. The
URL-shortener profile does not add business capabilities, and deterministic route validation uses
only HTTP method/path pairs explicitly stated in the original requirement.

### Phase 4 demos

The offline demo validates platform orchestration only. It deliberately continues to use the tiny
generic scripted fixture and writes `SCRIPTED_PLATFORM_TEST_DOUBLE` contract evidence; it is not a
production URL-shortener implementation or a substitute for the real OpenAI run.

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts/run_phase4_scripted_demo.ps1
~~~

The genuine acceptance script requires `LLM_MODE=OPENAI`, `OPENAI_API_KEY`, and `OPENAI_MODEL` in the
process environment. It checks presence without printing the key and prompts a human at every
approval gate—approval is never implicit or automatic.

~~~powershell
$env:LLM_MODE = 'OPENAI'
$env:OPENAI_API_KEY = '<set-locally>'
$env:OPENAI_MODEL = 'gpt-5.6-terra'
$env:OPENAI_REASONING_EFFORT = 'medium'
powershell -ExecutionPolicy Bypass -File scripts/run_phase4_openai_demo.ps1
~~~

The OpenAI run may incur provider charges and is intentionally not executed by the automated test
suite. `OPENAI_MAX_OUTPUT_TOKENS` defaults to `2500` to bound each structured response. Terra's
reasoning effort is explicit so latency, cost, and behavior do not depend on a provider default.

### Phase 4 verification

~~~powershell
python -m ruff check .
python -m pytest -q
python -m pytest tests/unit/test_scenario_resolver.py tests/unit/test_url_shortener_profile.py tests/unit/test_url_shortener_contract.py tests/unit/test_no_embedded_template.py -q
python -m pytest tests/integration/test_phase4_scripted_workflow.py tests/integration/test_url_shortener_contract_validation.py tests/integration/test_target_project_independence.py tests/integration/test_no_precreated_target.py -q
~~~

Current acceptance status:

~~~text
PHASE 4 PLATFORM SUPPORT — PASS
REAL SIX-AGENT OPENAI GREENFIELD RUN — PENDING USER EXECUTION
~~~

### Current limitations

The implemented specialization supports governed greenfield generation only. Brownfield repository
analysis, modification, migration, and release workflows are not supported yet. The OpenAI provider
has no browsing or arbitrary tool access, Git operations remain local, and automated tests never
make live OpenAI calls.
