# Risks, Trade-offs, and Limitations

## Assumptions

- A trusted local operator controls the host, approvals, and workspace root.
- Generated repositories are disposable local evidence, not production deployments.
- Git and Python 3.11+ are available.
- Scripted outputs are evaluation fixtures; live-model output is untrusted until validated.
- Final human reviewers own scope, approval, and engineering quality.

## Risk register

| Risk | Preventive control | Detective control | Recovery control | Evidence | Residual risk |
| --- | --- | --- | --- | --- | --- |
| Unauthorized path modification | Scenario/task allowlists and canonical PathPolicy | Policy audit details/tests | Safe stop | path_policy.py tests | Host-level privileged writes remain outside model boundary |
| Stale overwrite | SHA-256 expected_hash | HASH_MISMATCH/EDIT_CONFLICT | Refresh repository context and retry | ControlledEditor tests | External races need workspace leases |
| Source corruption | Governed copy; source read-only | Source hashes/Git status | Discard destination | Brownfield tests | Manual host edits remain possible |
| Database/secret copying | Copy exclusions and restricted names | Scanner/policy checks | Safe stop and recreate copy | workspace tests | Novel secret filenames may evade name rules |
| Unapproved high-risk change | HIGH_RISK_CHANGE interrupt | Approval/audit IDs | Reject or request changes | approval tests | Human review quality varies |
| Stale approval | Approval ID plus state version | INVALID_STATE_VERSION | Fetch current state | resume tests | Cross-store operations need stronger production transactions |
| Invalid task sequencing | PlanValidator and dependency readiness | TASK_DEPENDENCY_VIOLATION | Plan correction/replan | task-selection tests | Model plans can exhaust correction budget |
| Migration failure | Approved migration paths and Alembic runner | Upgrade cycle | Coding retry or rollback | migration tests/evidence | Production data migration scale not tested |
| Test regression | Task and final validation | Pytest/Ruff/OpenAPI | Retry/replan/rollback | integration suite | Coverage cannot prove absence of defects |
| Partial task completion | Transactional edit batch and task status | Completeness guard | Restore batch/retry | task-loop tests | External tools may have non-file side effects |
| Retry exhaustion | Per-stage bounded limits | RETRY_STARTED/exhausted events | Rollback or safe stop | retry tests | Manual restart may still be required |
| Unsafe live-model output | Typed schema and deterministic boundaries | AGENT_FAILED/policy evidence | Retry/replan/safe stop | provider tests | Novel invalid outputs remain possible |
| Concurrent modification | Hash guard | Mismatch conflict | Refresh context | editor tests | No distributed workspace lease |
| Clarification loops | Human answer gate | Clarification events | Manual stop | clarification tests | No semantic deduplication/max rounds |
| Missing dependency context | Scoped repository context | Task failure/validation | Refresh context and retry | repository-context tests | Cross-task context contract can be incomplete |

## Live-provider limitations

### Blocked zero-edit high-risk routing

Observed condition: status BLOCKED, structured_edits empty, high_risk_change true. Desired future
behavior is no high-risk approval, then retry or replan, followed by safe stop after exhaustion.
A related retry-plan validation correction predates Phase 5. The exact BLOCKED plus zero-edit
high-risk condition has not been proven resolved by a dedicated regression test and remains open.

### Dependency context

Downstream tasks may require authoritative dependency outputs—including current content and
SHA-256—as read-only context while current-task write ownership remains narrow. Existing-file and
retry contexts are improved, but complete semantic dependency propagation is not guaranteed.

### Clarification loops

Future controls should add semantic question deduplication, maximum clarification rounds, reuse of
approved answers, and human escalation or safe stop after repetition.

### Provider persistence

Execution mode and exact scripted scenario identity are not durably stored in workflow/audit rows.
Reliability reports therefore cannot filter provider and label historical scenario candidates by
profile rather than durable benchmark identity.

## Architecture trade-offs

SQLite, a local synchronous process, filesystem artifacts, and local Git made the prototype
reviewable within the 2–3 day assignment constraint. They trade away multi-node concurrency,
central retention, remote collaboration, and strong isolation. Controlled text editing is safer
than direct model writes but less language-aware than AST/LSP editing. Human approval constrains
autonomy but introduces latency and reviewer dependence.

## Roadmap

- **P0:** container/process isolation, workspace leases, durable provider/scenario metadata,
  blocked-zero-edit regression and routing rule, clarification round limits.
- **P1:** PostgreSQL, production checkpoint backend, worker queue, idempotency, tamper-evident audit
  export, secret manager, centralized telemetry.
- **P2:** AST/LSP-aware edits, policy-approved remote Git/PR integration, richer scenario plugins,
  statistically designed live-model evaluation.

Deferred: cloud deployment, UI, automatic alternate-provider fallback, distributed execution, and
enterprise compliance infrastructure.
