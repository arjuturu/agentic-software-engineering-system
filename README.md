# Agentic Software Engineering System

A governed local Agentic Software Engineering prototype that transforms requirements into
reviewable engineering outcomes. It combines structured model proposals, deterministic validation,
human approval gates, controlled repository changes, durable state, and evidence packaging.

> LLMs propose; deterministic controls decide. Humans approve high-impact transitions and own
> final quality.

## Quick Links

- [Architecture overview](deliverables/architecture-overview.md)
- [Assignment traceability](docs/assignment-traceability.md)
- [Orchestration model](deliverables/orchestration-model.md)
- [Three-scenario evidence index](docs/evidence-index.md)
- [Testing and validation](deliverables/testing-and-validation.md)
- [Risks, trade-offs, and limitations](deliverables/risks-tradeoffs-limitations.md)
- [Final engineering summary](deliverables/final-engineering-summary.md)
- [Recorded Ambiguous Scenario 3 video](https://drive.google.com/drive/folders/1OFURyh3AvgU3c7pBqPkgEXVUiKJN1zAz?usp=sharing)
- [Setup](#prerequisites-and-setup) and [interactive demo](#interactive-scripted-demo)

## Verified Results

| Verification | Result |
|---|---:|
| Platform test suite | 259 passed |
| Ruff | Passed |
| `git diff --check` | Passed |
| Greenfield selected workflow | READY |
| Brownfield selected workflow | READY |
| Ambiguous selected workflow | READY after clarification |

These results demonstrate the defined assignment scenarios and local prototype controls; they are
not presented as statistically meaningful production reliability.

## Core capabilities

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

### System components and responsibilities

| Component | Responsibility |
| --- | --- |
| Interaction layer | Swagger, API clients, and demo scripts |
| FastAPI control plane | HTTP lifecycle and safe errors |
| Workflow service | Workflow creation, resume, retry, and snapshots |
| Scenario resolver | Selects generic or URL-shortener policy profiles |
| LangGraph | Durable state graph and conditional routing |
| Provider abstraction | Typed model-output boundary |
| Scripted provider | Repeatable offline agent responses |
| OpenAI provider | Experimental native structured output |
| Human gates | Interrupt/resume with IDs and state versions |
| Deterministic controls | Plan, dependency, path, edit, test, and migration checks |
| Governed Execution Layer | Applies only validated, scoped local changes |
| Workflow database | Application metadata and audit history |
| Checkpoint database | LangGraph continuation state |
| Evidence layer | Versioned artifacts and reliability reports |

See the [system architecture diagram](deliverables/images/system-architecture.jpg) for the
component layout and numbered execution flows.

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
code from GitHub. The documented startup and demo commands explicitly set LLM_MODE to SCRIPTED so
a local environment override cannot unintentionally enable model calls.

OpenAI mode uses real model calls through the same typed schemas and deterministic governance. It
is non-deterministic and experimental: a workflow may clarify, block, retry, replan, roll back,
safely stop, or fail. OpenAI mode must be selected intentionally and may incur provider charges.
Never commit credentials.

## Agent Model

The recurring specialist roles are Requirement, Design, Planning, Coding, Validation,
Documentation, and Release. Brownfield additionally activates Repository Analysis. Each agent has
a focused responsibility and output schema; agents exchange typed, versioned workflow state and
artifacts rather than communicating through unrestricted peer-to-peer conversation.

LangGraph and `WorkflowService` are orchestrators, not agents. Workspace Manager, Repository
Scanner, `ControlledEditor`, Git, Alembic, Pytest, and Ruff are deterministic tools, not agents.
Deterministic controls own routing, approvals, path enforcement, edits, validation, rollback, and
safe stop.

Fewer agents would combine unrelated responsibilities, broaden prompts and permissions, and reduce
retry and audit granularity. More agents would add unnecessary coordination, latency, duplicated
context, and inconsistent decisions. A separate agent was created only where a task required a
distinct reasoning responsibility.

## Why LangGraph?

LangGraph was selected because the workflow behaves like a governed state machine rather than an
unconstrained agent conversation. The project needs persistent workflow state, conditional
routing, human clarification and approval interrupts, checkpoint resume, bounded retry loops,
replanning, rollback and safe stop, parallel final validation and documentation, synchronization
before release, and explicit decision lineage.

A simple sequential chain would not provide the same explicit control over interrupts, loops,
checkpoints, branch synchronization, and terminal safety.

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
$env:LLM_MODE = "SCRIPTED"
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
export LLM_MODE=SCRIPTED
python -m uvicorn app.main:app --reload
~~~

Swagger is at http://127.0.0.1:8000/docs. Health routes are GET /health/live and
GET /health/ready. Do not expose or commit .env. Scripted mode requires no OpenAI credential.

## Automatic scripted demo

Automatic mode uses deterministic scripted model responses, automatically answers the supported
clarification, and submits the workflow approval gates. It does not call OpenAI. The runner starts
and stops Uvicorn unless -UseExistingServer is supplied.

~~~powershell
$env:LLM_MODE = "SCRIPTED"

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
$env:LLM_MODE = "SCRIPTED"

powershell -ExecutionPolicy Bypass -File scripts/run_phase4_scripted_demo.ps1 -Mode Interactive -Scenario Greenfield -WorkspacePrefix interactive-demo
powershell -ExecutionPolicy Bypass -File scripts/run_phase4_scripted_demo.ps1 -Mode Interactive -Scenario Brownfield -WorkspacePrefix interactive-demo -SourceWorkspace 'your-greenfield-workspace-name'
powershell -ExecutionPolicy Bypass -File scripts/run_phase4_scripted_demo.ps1 -Mode Interactive -Scenario Ambiguous -WorkspacePrefix interactive-demo -SourceWorkspace 'your-greenfield-workspace-name'
~~~

`SourceWorkspace` expects the workspace directory name relative to `WORKSPACE_ROOT`. It must not
receive an absolute filesystem path. Filesystem operations use the full workspace path; workflow
API requests use only the workspace directory name as `sourceWorkspace`.

For example, if the returned `workspacePath` is
`C:\Code\agentic-url-shortner\workspace\interactive-demo\interactive-demo-greenfield-123`, the
correct `sourceWorkspace` value is `interactive-demo-greenfield-123`.

## Testing from Swagger UI

Start the API and open http://127.0.0.1:8000/docs:

~~~powershell
$env:LLM_MODE = "SCRIPTED"
python -m uvicorn app.main:app --reload
~~~

Expand POST /api/v1/workflows, select **Try it out**, and submit one of the following bodies.
Use a unique workspaceName for every run. These Swagger examples use scriptedScenario values and
therefore require the scripted server mode shown above.

<details>
<summary>Show Swagger request and response examples</summary>

### Greenfield request

~~~json
{
  "scenarioType": "GREENFIELD",
  "requirement": "Build a local URL-shortening API using FastAPI, SQLite, SQLAlchemy 2.x, and Alembic. Support POST /api/v1/urls and GET /{short_code}. Generate secure eight-character alphanumeric short codes using Python secrets. Retry collisions no more than five times. Return the approved exact 404 and 503 responses. Include tests and documentation. Do not add aliases, analytics, expiration, authentication, caching, UI, messaging, workers, or cloud deployment.",
  "workspaceName": "swagger-greenfield",
  "scriptedScenario": "URL_SHORTENER_GREENFIELD_HAPPY_PATH"
}
~~~

Wait for the Greenfield workflow to reach READY. From the returned `workspacePath`, extract only
the final directory name and pass that name as `sourceWorkspace` for the Brownfield and Ambiguous
requests. `sourceWorkspace` must be relative to `WORKSPACE_ROOT` and must not be an absolute
filesystem path. Those scenarios create separate destination workspaces from the same Greenfield
source.

Filesystem operations use the full workspace path. Workflow API requests use only the workspace
directory name as `sourceWorkspace`.

### Brownfield request

~~~json
{
  "scenarioType": "BROWNFIELD",
  "requirement": "Enhance the existing URL-shortener application with click analytics. Add a click_count column with a default value of 0. Increment click_count on every successful redirect. Add GET /api/v1/urls/{short_code}/stats. Create a new Alembic migration. Preserve existing creation, validation, collision, and redirect behavior. Add regression tests. Do not add aliases, expiration, authentication, caching, messaging, workers, UI, or cloud deployment.",
  "workspaceName": "swagger-brownfield",
  "scriptedScenario": "URL_SHORTENER_BROWNFIELD_ANALYTICS",
  "sourceWorkspace": "replace-with-greenfield-workspace-name"
}
~~~

### Ambiguous request

~~~json
{
  "scenarioType": "AMBIGUOUS",
  "requirement": "Add support for optional custom aliases. Aliases should be user-friendly, unique, and handled safely.",
  "workspaceName": "swagger-ambiguous",
  "scriptedScenario": "URL_SHORTENER_AMBIGUOUS_ALIASES",
  "sourceWorkspace": "replace-with-greenfield-workspace-name"
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

</details>

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

### Reliability Interpretation

- Historical Phase 5 dataset: 18 workflows, a 27.78% aggregate historical READY rate, and mixed
  development, retry, rollback, safe-stop, and live-model evidence.
- Phase 6 interactive dataset: 5 persisted workflows, 4 READY, 1
  `WAITING_FOR_CLARIFICATION`, and an 80% aggregate READY rate.

The selected Greenfield, Brownfield, and completed Ambiguous workflows reached READY. The waiting
Ambiguous record demonstrates the clarification boundary and is not a failed workflow; the dataset
also contains an additional successful Brownfield run. Neither dataset is statistically meaningful
production reliability, and the interactive dataset is not a clean three-workflow benchmark.

MTTR is not currently measurable because no canonical incident-start and resolution-completion
timestamp pair is persisted. No substitute metric is relabeled as MTTR.

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

## Current Boundaries and Future Enhancements

The current implementation is a local, single-node prototype intended to demonstrate controlled
autonomy, SDLC orchestration, deterministic validation, and safe change management. It is not
presented as a complete production deployment.

### Governed Git and PR integration

Remote Git and pull-request automation were intentionally deferred until local governed editing,
validation, rollback, and audit controls were proven. The current system already produces the
diffs, checkpoints, test evidence, and release summary required for a future governed PR workflow.

A future GitHub/GitLab adapter or Git MCP would create short-lived branches, push only after
validation, open pull requests, and attach test, architecture, audit, and release evidence. It
would enforce a repository allowlist, least-privilege credentials, branch protections, CI status
checks, and human approval before merge, with no default auto-merge.

### Additional future enhancements

- Container-isolated execution.
- PostgreSQL-backed state and distributed workspace leases, plus worker queues.
- RBAC, policy-as-code, secrets management, OpenTelemetry, and centralized audit retention.
- SAST, dependency scanning, and SBOM generation.
- Durable provider identity, exact scenario identity, and incident timestamps required for MTTR.
- AST- or LSP-aware editing.
- Multi-language and multi-repository support.

See [risks, trade-offs, and limitations](deliverables/risks-tradeoffs-limitations.md) for the
detailed production boundaries and roadmap.
