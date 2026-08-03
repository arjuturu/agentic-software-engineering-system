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

## Automatic scripted demo

Automatic mode uses deterministic scripted model responses, automatically answers the supported
clarification, and submits the workflow approval gates. It does not call OpenAI. The runner starts
and stops Uvicorn unless -UseExistingServer is supplied.

~~~powershell
# Run Greenfield, Brownfield, and Ambiguous in sequence.
powershell -ExecutionPolicy Bypass -File scripts/run_phase4_scripted_demo.ps1 -Mode Automatic -Scenario All -WorkspacePrefix automatic-demo

# Run an individual scenario.
powershell -ExecutionPolicy Bypass -File scripts/run_phase4_scripted_demo.ps1 -Mode Automatic -Scenario Greenfield -WorkspacePrefix automatic-demo
powershell -ExecutionPolicy Bypass -File scripts/run_phase4_scripted_demo.ps1 -Mode Automatic -Scenario Brownfield -WorkspacePrefix automatic-demo -SourceWorkspace 'your-greenfield-workspace-name'
powershell -ExecutionPolicy Bypass -File scripts/run_phase4_scripted_demo.ps1 -Mode Automatic -Scenario Ambiguous -WorkspacePrefix automatic-demo -SourceWorkspace 'your-greenfield-workspace-name'
~~~

Brownfield and Ambiguous require a successful Greenfield source. If -SourceWorkspace is omitted
for either scenario, the runner first creates a fresh Greenfield source.

## Interactive scripted demo

Interactive mode uses the same deterministic workflow but asks the evaluator to answer
clarifications and make approval decisions.

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts/run_phase4_scripted_demo.ps1 -Mode Interactive -Scenario Greenfield -WorkspacePrefix interactive-demo
powershell -ExecutionPolicy Bypass -File scripts/run_phase4_scripted_demo.ps1 -Mode Interactive -Scenario Brownfield -WorkspacePrefix interactive-demo -SourceWorkspace 'your-greenfield-workspace-name'
powershell -ExecutionPolicy Bypass -File scripts/run_phase4_scripted_demo.ps1 -Mode Interactive -Scenario Ambiguous -WorkspacePrefix interactive-demo -SourceWorkspace 'your-greenfield-workspace-name'
~~~

SourceWorkspace is the directory name relative to WORKSPACE_ROOT, never an absolute path.
Filesystem inspection commands may use the full generated workspace path.

## Testing from Swagger UI

Start the API and open http://127.0.0.1:8000/docs:

~~~powershell
python -m uvicorn app.main:app --reload
~~~

Expand POST /api/v1/workflows, select **Try it out**, and submit one of the following bodies.
Use a unique workspaceName for every run.

### Greenfield request

~~~json
{
  "scenarioType": "GREENFIELD",
  "requirement": "Build a local URL-shortening API using FastAPI, SQLite, SQLAlchemy 2.x, and Alembic. Support POST /api/v1/urls and GET /{short_code}. Generate secure eight-character alphanumeric short codes using Python secrets. Retry collisions no more than five times. Return the approved exact 404 and 503 responses. Include tests and documentation. Do not add aliases, analytics, expiration, authentication, caching, UI, messaging, workers, or cloud deployment.",
  "workspaceName": "swagger-greenfield",
  "scriptedScenario": "URL_SHORTENER_GREENFIELD_HAPPY_PATH"
}
~~~

Wait for the Greenfield workflow to reach READY. Copy its workspacePath value into sourceWorkspace
for the Brownfield and Ambiguous requests. Those scenarios create separate destination workspaces
from the same Greenfield source.

### Brownfield request

~~~json
{
  "scenarioType": "BROWNFIELD",
  "requirement": "Enhance the existing URL-shortener application with click analytics. Add a click_count column with a default value of 0. Increment click_count on every successful redirect. Add GET /api/v1/urls/{short_code}/stats. Create a new Alembic migration. Preserve existing creation, validation, collision, and redirect behavior. Add regression tests. Do not add aliases, expiration, authentication, caching, messaging, workers, UI, or cloud deployment.",
  "workspaceName": "swagger-brownfield",
  "scriptedScenario": "URL_SHORTENER_BROWNFIELD_ANALYTICS",
  "sourceWorkspace": "replace-with-greenfield-workspacePath"
}
~~~

### Ambiguous request

~~~json
{
  "scenarioType": "AMBIGUOUS",
  "requirement": "Add support for optional custom aliases. Aliases should be user-friendly, unique, and handled safely.",
  "workspaceName": "swagger-ambiguous",
  "scriptedScenario": "URL_SHORTENER_AMBIGUOUS_ALIASES",
  "sourceWorkspace": "replace-with-greenfield-workspacePath"
}
~~~

Use GET /api/v1/workflows/{workflow_id} to retrieve the latest status and IDs. When
pendingApproval is present, open
POST /api/v1/workflows/{workflow_id}/approvals/{approval_id} and copy gateType and stateVersion
from that latest response:

~~~json
{
  "type": "APPROVAL_DECISION",
  "gateType": "REQUIREMENT",
  "stateVersion": 1,
  "action": "APPROVE",
  "comments": "Approved through Swagger UI",
  "conditions": [],
  "decidedBy": "local-reviewer"
}
~~~

Repeat this step for each pending approval, always using the current gate type, approval ID, and
state version. For the Ambiguous scenario, open
POST /api/v1/workflows/{workflow_id}/clarifications when pendingInteraction is present. Copy the
workflow ID, clarification ID, state version, and exact question IDs from the latest response:

~~~json
{
  "type": "CLARIFICATION_RESPONSE",
  "workflowId": "WF-...",
  "clarificationId": "CLR-...",
  "stateVersion": 2,
  "answers": [
    {
      "questionId": "Q-ALIAS-001",
      "answer": "The custom alias is optional. When omitted, retain generated short-code behavior."
    },
    {
      "questionId": "Q-ALIAS-002",
      "answer": "Allow lowercase letters, digits, hyphen, and underscore only."
    },
    {
      "questionId": "Q-ALIAS-003",
      "answer": "Aliases must contain between 4 and 30 characters."
    },
    {
      "questionId": "Q-ALIAS-004",
      "answer": "Normalize aliases to lowercase before validation and persistence. Alias uniqueness is case-insensitive. Generated short codes and aliases share the same short_code namespace."
    },
    {
      "questionId": "Q-ALIAS-005",
      "answer": "Return HTTP 409 with detail Custom alias already exists."
    },
    {
      "questionId": "Q-ALIAS-006",
      "answer": "Reserve api, docs, openapi.json, and health."
    }
  ]
}
~~~

Include one answer for every returned question. After each submission, use the newest response
values; stale state versions are rejected.

## Verification

~~~powershell
python -m pytest -q
python -m ruff check app tests scripts
git diff --check
~~~

The final verification result is recorded in
[testing and validation](deliverables/testing-and-validation.md).

## Reliability reporting

~~~powershell
python scripts/generate_reliability_report.py
python scripts/generate_reliability_report.py --scenario-type GREENFIELD --output-json evidence/08-reliability/reliability-metrics.json --output-markdown docs/reliability-metrics.md
~~~

## Final evidence

Review the architecture, scenario diagrams, key results, and detailed document references in the
[Final Evidence Summary](deliverables/Final%20Evidence%20Summary.md).

Artifacts produced by the agents for the Greenfield, Brownfield, and Ambiguous in interactive mode
are available in
[generated_artifacts/interactive-mode-evidences-for-3-scenarios](generated_artifacts/interactive-mode-evidences-for-3-scenarios/).
Each workflow's evidence is organized in its corresponding WF-... directory.

### Screenshot and video evidence

- [Screenshot evidence for all three scenarios](deliverables/three-scenario-screenshot-evidence.pdf)
- [Ambiguous Scenario 3 video demonstration](https://drive.google.com/drive/folders/1OFURyh3AvgU3c7pBqPkgEXVUiKJN1zAz?usp=sharing)

Due to the evaluation time constraints, only the Ambiguous scenario was recorded as a video. The
PDF contains screenshot evidence for Greenfield, Brownfield, and Ambiguous.
