# Architecture Overview

## Layers

| Layer | Components | Source mapping |
| --- | --- | --- |
| Interaction Layer | Swagger, API clients, demo runners | app/main.py, app/api/, scripts/run_phase4_scripted_demo.ps1 |
| Control Plane | FastAPI, WorkflowService, scenario resolution | app/main.py, app/services/workflow_service.py, app/scenarios/resolver.py |
| Model Provider Layer | AgentRunner, ScriptedProvider, OpenAIProvider | app/agents/runner.py, app/agents/scripted_provider.py, app/agents/openai_provider.py |
| Governance and Orchestration | LangGraph, agents, gates, routing, failure controls | app/orchestration/, app/agents/ |
| Governed Execution Layer | workspace copy, scan, edit, Git, commands, tests, Alembic | app/tools/ |
| State and Evidence | workflow DB, checkpoint DB, artifacts, audit, reliability | app/database/, app/artifacts/, app/services/reliability_metrics.py |

The complete component view is shown below:

![System architecture component and workflow diagram](images/system-architecture.jpg)

## Numbered flow

1. **A — Interaction:** a user, Swagger/Postman, or the demo runner submits a scenario and
   requirement.
2. **B — Control Plane:** FastAPI validates the request; WorkflowService resolves the scenario,
   creates durable workflow metadata, invokes LangGraph, and returns a snapshot.
3. **C — Provider:** agents call the typed provider abstraction. Scripted mode supplies
   deterministic responses; OpenAI mode requests native structured output.
4. **D — Governance:** agent proposals pass schema, plan, dependency, approval, state-version,
   scenario, and failure-routing controls.
5. **E — Governed Execution:** repository scanning, workspace copying, hash-guarded editing,
   local Git, tests, and migrations act only inside validated workspace boundaries.
6. **F — State and Evidence:** application records, LangGraph checkpoints, versioned artifacts,
   audit events, generated repositories, and reliability reports preserve lineage.

Failure Routing has four explicit exits:

- **D.4.1 Retry:** rerun the current task within configured bounds.
- **D.4.2 Replan:** invalidate affected downstream state and revisit Requirement, Design, or Plan.
- **D.4.3 Rollback:** restore the governed Git baseline and persist rollback evidence.
- **D.4.4 Safe Stop:** terminate cleanly with a sanitized error and recovery recommendation.

## Key decisions

| Decision | Rationale | Trade-off and production evolution |
| --- | --- | --- |
| LangGraph rather than linear chaining | Interrupt/resume, conditional routing, loops, joins, and durable checkpoints are first-class | Adds graph/state complexity; production needs operational checkpoint tooling |
| Separate workflow and checkpoint stores | Queryable application/audit metadata remains independent of continuation internals | Cross-store agreement must be tested; production needs transactional coordination |
| ControlledEditor | Prevents model output from becoming unrestricted filesystem access | Text edits are less semantic than AST/LSP operations |
| Governed source copying | Preserves Brownfield source immutability and removes remotes/secrets/caches | Copies cost time/storage; production needs leases and content-addressed snapshots |
| Scripted evaluation | Repeatable, offline evidence exercises real deterministic controls | Does not predict arbitrary live-model behavior |
| SQLite | Simple, inspectable, sufficient for a time-boxed single-node prototype | PostgreSQL, concurrency control, backups, and migrations are required at scale |

## Production-scale changes

Move workflow metadata to PostgreSQL; use a supported distributed checkpoint store; introduce
worker queues, idempotency keys, workspace leases, isolated containers, resource quotas,
tamper-evident audit retention, centralized logs/metrics, secret management, and policy-reviewed
remote Git integrations. Horizontal scalability has not been demonstrated.
