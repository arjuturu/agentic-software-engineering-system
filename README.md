# Agentic Software Engineering System

A governed local Agentic Software Engineering prototype that transforms requirements into
reviewable engineering outcomes. It combines structured model proposals, deterministic validation,
human approval gates, controlled repository changes, durable state, and evidence packaging.

> LLMs propose; deterministic controls decide. Humans approve high-impact transitions and own
> final quality.

## Assignment capabilities

- Requirement analysis, normalization, ambiguity detection, and clarification.
- Design and dependency-aware Planning Agents with validated structured outputs.
- Stateful, non-linear LangGraph orchestration with sequential task execution and a parallel
  validation/documentation join.
- Greenfield creation plus repository-aware Brownfield and Ambiguous source-copy workflows.
- Requirement, architecture/plan, high-risk-change, and release approvals.
- Task-scoped path ownership, repository scanning, hash-guarded ControlledEditor operations,
  local-only Git checkpoints, migrations, tests, and target contract validation.
- Bounded retry, plan correction, replanning, rollback, safe stop, audit events, artifacts, and
  reliability reporting.

## Architecture

| Component | Responsibility | Main implementation |
| --- | --- | --- |
| Interaction layer | Swagger, API clients, and demo scripts | app/main.py, app/api/, scripts/ |
| FastAPI control plane | HTTP lifecycle and safe errors | app/main.py, app/api/ |
| Workflow service | Workflow creation, resume, retry, snapshots | app/services/workflow_service.py |
| Scenario resolver | Selects generic or URL-shortener policy profiles | app/scenarios/resolver.py |
| LangGraph | Durable state graph and conditional routing | app/orchestration/graph.py |
| Provider abstraction | Typed model-output boundary | app/agents/provider.py |
| Scripted provider | Repeatable offline agent responses | app/agents/scripted_provider.py |
| OpenAI provider | Experimental native structured output | app/agents/openai_provider.py |
| Human gates | Interrupt/resume with IDs and state versions | app/orchestration/approvals.py |
| Deterministic controls | Plan, dependency, path, edit, test, and migration checks | app/orchestration/, app/tools/ |
| Governed Execution Layer | Applies only validated, scoped local changes | app/tools/controlled_editor.py |
| Workflow database | Application metadata and audit history | app/database/models/ |
| Checkpoint database | LangGraph continuation state | app/orchestration/checkpoint.py |
| Evidence layer | Versioned artifacts and reliability reports | app/artifacts/, app/services/reliability_metrics.py |

## Scenario topology

- Greenfield: Design and Planning complete before creation of an empty governed workspace.
- Brownfield: a successful Greenfield workspace is validated, copied to a separate destination,
  and analyzed before Design and Planning.
- Ambiguous: clarification completes before source copying, repository analysis, Design, Planning,
  or Coding.

Brownfield and Ambiguous independently branch from the same Greenfield baseline; Ambiguous does
not build on Brownfield.

## Scripted and OpenAI modes

Scripted mode uses deterministic pre-authored model responses, makes no OpenAI calls, and exercises
the real orchestration, approvals, Git, ControlledEditor, migrations, tests, artifacts, audit, and
release gates. It is the recommended repeatable evaluation mode and does not download generated
code from GitHub.

OpenAI mode uses real model calls through the same typed schemas and deterministic governance. It
is non-deterministic and experimental: a workflow may clarify, block, retry, replan, roll back,
safely stop, or fail. Never commit credentials.

## Prerequisites and setup

- Python 3.11 or newer
- Git on PATH
- PowerShell for the supplied demonstration runner

Windows PowerShell:

~~~powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python scripts/init_local.py
alembic upgrade head
python scripts/verify_environment.py
python -m uvicorn app.main:app --reload
~~~

macOS/Linux:

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python scripts/init_local.py
alembic upgrade head
python scripts/verify_environment.py
python -m uvicorn app.main:app --reload
~~~

Swagger is at http://127.0.0.1:8000/docs. Health routes are GET /health/live and
GET /health/ready. Do not expose or commit .env. Scripted mode requires no OpenAI credential.

## Interactive scripted demo

The completed Phase 6 evidence should be reviewed rather than rerun solely for regeneration.
For a fresh, explicitly requested evaluation:

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts/run_phase4_scripted_demo.ps1 -Mode Interactive -Scenario Greenfield -WorkspacePrefix demo
powershell -ExecutionPolicy Bypass -File scripts/run_phase4_scripted_demo.ps1 -Mode Interactive -Scenario Brownfield -WorkspacePrefix demo -SourceWorkspace phase6-interactive-greenfield-20260803182759430
powershell -ExecutionPolicy Bypass -File scripts/run_phase4_scripted_demo.ps1 -Mode Interactive -Scenario Ambiguous -WorkspacePrefix demo -SourceWorkspace phase6-interactive-greenfield-20260803182759430
~~~

SourceWorkspace is the directory name relative to WORKSPACE_ROOT, never an absolute path.
Filesystem inspection commands may use the full generated workspace path.

## Verification

~~~powershell
python -m pytest -q
python -m ruff check app tests scripts
git diff --check
~~~

The Phase 6 result is recorded in
[testing and validation](deliverables/testing-and-validation.md).

## Reliability reporting

~~~powershell
python scripts/generate_reliability_report.py
python scripts/generate_reliability_report.py --scenario-type GREENFIELD --output-json evidence/08-reliability/reliability-metrics.json --output-markdown docs/reliability-metrics.md
~~~

## Final evidence

Review the architecture, scenario diagrams, key results, and detailed document references in the
[Final Evidence Summary](deliverables/Final%20Evidence%20Summary.md).
