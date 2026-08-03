# Orchestration Model

## Stateful graph

EngineeringWorkflowState in app/orchestration/state.py carries IDs, scenario policy, requirements,
versioned Design and Planning outputs, the active task, dependency status, repository context,
change plan, approvals, retries, validation branches, artifacts, and terminal status. The
SqliteSaver in app/orchestration/checkpoint.py persists graph continuation by thread ID separately
from application metadata.

The graph in app/orchestration/graph.py is non-linear:

1. Requirement Agent proposes analysis.
2. Ambiguity routes through prepare_clarification and clarification_gate, then returns to the
   Requirement Agent.
3. Approved requirements route to Design and Planning.
4. PlanValidator either permits architecture/plan approval, requests bounded Planning correction,
   or safe-stops.
5. Greenfield prepares a new workspace after architecture approval. Brownfield/Ambiguous validate
   and copy the source after requirement approval, scan it, then run Design and Planning.
6. Coding selects the first dependency-ready unfinished task, validates path ownership, obtains
   high-risk approval when required, applies edits, and performs task-local validation.
7. complete_task loops to Coding until all required executable tasks are complete.
8. Final Validation and draft Documentation execute as parallel branches and synchronize at
   validation_join.
9. Failure classification selects retry, replan, rollback, or safe stop.
10. Documentation/Release prepares the final release gate and a human selects the terminal result.


## Gates and resume safety

| Gate | Entry evidence | Resume validation | Exit |
| --- | --- | --- | --- |
| Clarification | Persisted pending questions and expected state version | Workflow ID, clarification ID, version, response type, exact unique question IDs | Requirement re-analysis |
| Requirement | Versioned requirement analysis | Approval ID, gate type, state version, allowed action | Design or source preparation |
| Architecture and Plan | Validated Design and plan artifacts | Approval ID, gate type, state version, action | Workspace or Git checkpoint |
| High Risk Change | Current validated structured edit plan | Approval ID/version/action for that plan | Apply current plan |
| Release | Joined validation and release package | Approval ID/version/action | READY, READY_WITH_CONDITIONS, NOT_READY, or rollback |

Approval decisions and clarification answers are persisted exactly once. State-version checks reject
stale submissions. Versioned artifacts and audit events preserve decision lineage without allowing
agents to approve their own work.

## Dependencies, sequencing, and ownership

PlanTask uses the canonical SETUP, IMPLEMENTATION, INTEGRATION, MIGRATION, TESTING,
DOCUMENTATION, and VALIDATION types. PlanValidator requires exact task IDs, complete execution
order, valid dependencies, explicit file allowlists for code-changing tasks, and scenario-policy
compatibility. app/orchestration/tasks.py selects only dependency-ready unfinished tasks in approved
execution order. Each task owns explicit expected/allowed files; dependency outputs may be supplied
as read-only context.

Intermediate validation is task-aware. An incomplete application is not judged as a final release:
unfinished work routes to the next executable task. Final validation begins only when
all_required_tasks_completed is true.

## Deterministic controls and human decisions

- **Model proposal:** typed Requirement, Design, Planning, Coding, Validation, and Release output.
- **Deterministic validation:** Pydantic parsing, PlanValidator, dependency selection, PathPolicy,
  hash checks, ControlledEditor, command allowlist, target contracts, tests, Ruff, and Alembic.
- **Human decision:** explicit approval IDs and versioned approve/change/reject actions.
- **Controlled execution:** only validated changes are applied by the Governed Execution Layer.

## Failure and recovery

- RetryPolicy applies per-stage configured limits and never retries policy/security failures.
- Plan correction returns exact structural violations to Planning without silently rewriting IDs.
- Replanning marks affected downstream outputs stale and increments the relevant version.
- Rollback restores the baseline commit and emits ROLLBACK_STARTED/ROLLBACK_COMPLETED.
- Safe stop emits SAFE_STOP_TRIGGERED and a recovery artifact.

Fallback is implemented through controlled retry, replan, rollback, and safe stop—not automatic
alternate-provider switching.

## Auditability qualification

The implementation preserves workflow/task IDs, state/stage, versioned artifacts, approval IDs,
clarifications, decisions, retries, rollback/safe-stop events, Git checkpoints, and reports. This is
strong local traceability. It is not tamper-evident storage, cryptographically signed audit history,
central retention, an immutable compliance archive, or SIEM integration.
