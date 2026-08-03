# Final Engineering Summary

## Requirement-to-release outcome

Requirement Agents normalize scope and identify ambiguity; the Ambiguous scenario proves a real
clarification pause and resume. Planning produces typed tasks with explicit IDs, dependencies,
order, paths, acceptance criteria, and validation commands. Brownfield analysis uses a governed
copy and bounded scanner to identify impacted modules, APIs, persistence, and data flow before
Design and Planning.

LangGraph makes orchestration stateful and non-linear. Requirement, Design, Planning, workspace,
Coding, task validation, failure handling, final validation/documentation, and release are
sequential where one result is a prerequisite. Final Validation and Documentation are parallel
branches; validation_join synchronizes them. The checkpoint state carries cross-stage context;
workflow IDs, versions, task IDs, approval IDs, audit events, artifact references, and Git commits
preserve decision lineage.

Humans intervene at requirement, architecture/plan, high-risk-change, and release boundaries.
Agents never approve their own work. PathPolicy, PlanValidator, dependency selection,
ControlledEditor, expected hashes, local-only Git, command allowlists, tests, Ruff, OpenAPI, and
Alembic form the Governed Execution Layer.

Retries are bounded per stage. Fixable planning defects return structured violations to Planning.
Replanning marks affected downstream results stale. Rollback restores the governed baseline. Safe
stop terminates with audit and recovery evidence. “Fallback” means these deterministic paths, not
automatic provider switching.

## Reliability

Success rate is READY divided by included workflows. Retry frequency uses authoritative retry/plan
correction events; rollback frequency requires explicit rollback evidence; end-to-end latency is
completed_at minus started_at.

MTTR is not currently measurable because the persistence model does not store a canonical
incident-start and resolution-completion timestamp pair. The system reports workflow duration,
time to READY, time to failure, retry counts, rollback counts, and safe-stop counts. No substitute
metric is relabeled as MTTR.

Historical Phase 5 evidence contains 18 mixed development records, 5 READY, a 27.78% aggregate
READY rate, retries, rollbacks, and safe stops. Phase 6 interactive evidence contains five records:
four READY and one WAITING_FOR_CLARIFICATION, for 80%. The selected Greenfield, Brownfield, and
completed Ambiguous candidates are READY. Samples are not production reliability.

## Engineering decision table

| Decision | Alternative | Why selected | Trade-off | 2–3 day effect | Production evolution |
| --- | --- | --- | --- | --- | --- |
| LangGraph | Linear agent chain | Durable interrupts, loops, routing, join | State complexity | Reused explicit graph primitives | Operational graph tooling |
| Scripted evaluation | Live-only | Repeatable offline proof of controls | Not live variability | Enabled stable assignment demo | Designed live benchmark |
| SQLite | PostgreSQL | Zero-service local setup | Single-node concurrency | Fast, inspectable persistence | PostgreSQL and HA |
| Governed local copy | Remote Git clone/PR | Source immutability and no network | Extra disk/time | Safe Brownfield evidence | Leased snapshots and PR integration |
| ControlledEditor | Direct model writes | Deterministic path/hash enforcement | Text-level semantics | Strong safety quickly | AST/LSP transformations |
| Hash guard | AST conflict resolution | Universal stale-write detection | Requires refresh/retry | Small implementation | Semantic merge service |
| Human gates | Unrestricted autonomy | Explicit accountability | Latency | Defensible governance | Risk-tiered approval policy |
| Local process | Containers | Minimal local prerequisites | Weaker isolation | Feasible in assignment | Sandboxed workers/containers |
| Scenario validators | Fully generic support | Strong URL-shortener evidence | Narrow scope | Demonstrable quality | Extensible validator plugins |

## Assumptions, deferrals, and ownership

The trusted local operator supplies approvals and controls the host. Generated repositories are
review artifacts. SQLite, local Git, and scripted evaluation are deliberate time-boxed choices.
Distributed workers, production databases, leases, container isolation, remote Git, deployment,
tamper-evident audit, and enterprise telemetry were deferred.

Agents operate within explicit autonomy boundaries.
Deterministic controls enforce change policy.
Humans own approval, oversight, and final engineering quality.
