# Codex Context Handoff

Updated: 2026-08-02

## Start Here

This repository contains cumulative, uncommitted Phase 3 and Phase 4 fixes. Preserve the current worktree and inspect `git status --short` before editing. Do not revert unrelated changes.

For the next Codex context:

1. Read this file and `CODEX_VERIFICATION_STATUS.md`.
2. Do not read or modify `.env`.
3. Do not manually edit workflow database rows or LangGraph checkpoints.
4. Do not call OpenAI unless the user explicitly authorizes a paid call.
5. Do not begin Phase 5 unless explicitly requested.
6. Apply schema changes with `alembic upgrade head` when working with a persistent local database.

## Current Verification Baseline

- Full test suite: 172 passed, 2 skipped.
- Skips: Windows host does not permit symbolic-link creation for two safety tests.
- Ruff: passed.
- `git diff --check`: passed.
- Checkpoint restart suite: 2 passed.
- No OpenAI HTTP calls were made during these fixes.

## Completed Fixes

### 1. Clarification Pause and Resume Version Consistency

Historical workflow: `WF-9807D51215AA`.

The clarification path now separates side effects from the interrupt boundary:

```text
requirement_agent
-> prepare_clarification
-> clarification_gate
-> requirement_agent
```

Key invariants while waiting:

- `workflow_runs.state_version`
- LangGraph checkpoint `state_version`
- `pendingInteraction.payload.stateVersion`
- clarification endpoint accepted version

All use the same authoritative pending version. Clarification answers, database version advancement, and `CLARIFICATION_SUBMITTED` are transactional and idempotent.

### 2. Design Agent Structured Output and Retry Recovery

Historical workflow: `WF-47E839A422EC`.

Implemented:

- Native OpenAI structured output through `with_structured_output(..., method="json_schema")`.
- Local strict-schema compatibility checks without an OpenAI call.
- Sanitized provider diagnostics including agent, exception class, Pydantic field paths/types, finish reason, token usage, and whether an HTTP request occurred.
- Design Agent failure transitions to `RETRYING` or a terminal safe state rather than remaining `RUNNING`.
- Controlled recovery for legacy failed Design checkpoints without repeating requirement approval.
- Retry attempt and approval decision idempotency.

### 3. Retry Audit Lifecycle Standardization

Controlled Design retry now uses the standard lifecycle:

```text
AGENT_FAILED
-> RETRY_STARTED
-> AGENT_RETRY_RECOVERED
-> AGENT_STARTED attempt 2
-> AGENT_COMPLETED
```

`RETRY_STARTED` is transactionally ensured before graph resume and is not duplicated when already emitted, when a request is repeated, or when the workflow is not retryable.

Legacy retry details are:

```json
{
  "agent": "DESIGN_AGENT",
  "retry_count": 1,
  "source": "LEGACY_FAILED_CHECKPOINT"
}
```

### 4. Cross-Workflow Clarification Isolation

Clarification identity is now scoped by both:

- `workflow_id`
- `clarification_id`

The clarification request body must include:

```json
{
  "workflowId": "WF-...",
  "clarificationId": "CLR-...",
  "stateVersion": 2,
  "answers": []
}
```

Path workflow ID, body workflow ID, checkpoint identity, and stored identity must agree. A clarification found only under another workflow returns `CLARIFICATION_NOT_FOUND`. Duplicate submission returns `CLARIFICATION_ALREADY_SUBMITTED` only for the matching workflow record.

Migration `002_clarification_scope` adds `workflow_requirements.clarification_id`, backfills existing IDs from JSON, and creates a composite unique constraint on `(workflow_id, clarification_id)` without changing checkpoint IDs.

### 5. Design Task Satisfaction and Repository Path Policy

Historical workflow: `WF-D0EC3E49B81C`.

After `ARCHITECTURE_AND_PLAN` approval, Design tasks whose criteria are fulfilled by architecture/plan artifacts remain in the plan but are marked `COMPLETED`. A `TASK_SATISFIED` audit event records the completion source.

Path policy now uses one workspace-relative POSIX representation and resolves:

1. Global workspace safety.
2. Non-empty scenario restrictions.
3. Approved task `allowed_paths`.
4. ControlledEditor validation.

An empty scenario `allowed_paths` means no additional scenario restriction. Legacy allowlist notation such as `/architecture_plan.txt` is normalized as a workspace-root policy declaration, while absolute edit paths remain blocked.

Traversal, drive paths, unrestricted absolute paths, restricted files, symlink escapes, and workspace escapes remain blocked.

Safe-stop policy evidence is sanitized and may include:

```json
{
  "attempted_path": "architecture_plan.txt",
  "normalized_path": "architecture_plan.txt",
  "task_id": "TASK-001",
  "task_allowed_paths": ["architecture_plan.txt"],
  "scenario_allowed_paths": [],
  "effective_allowed_paths": ["architecture_plan.txt"],
  "policy_rule": "EFFECTIVE_ALLOWED_PATHS"
}
```

### 6. Dependency-Aware Coding Task Selection

Historical workflow: `WF-9358BEFB491B`.

Coding selects the first unfinished task that:

- Has a supported executable task type.
- Has all dependencies marked `COMPLETED` or `SATISFIED`.
- Appears earliest in approved `execution_order` among eligible tasks.

Supported task types:

- setup
- implementation
- testing
- test (legacy alias)
- validation
- migration
- documentation

Completed Design/Planning artifact tasks remain excluded. `CODING_TASK_SELECTED` and `CHANGE_PLAN_CREATED` include sanitized selection evidence:

```json
{
  "task_id": "TASK-001",
  "task_type": "setup",
  "dependency_status": "READY",
  "dependencies": [],
  "incomplete_dependencies": []
}
```

If unfinished tasks remain but none are dependency-ready, the workflow routes directly to safe stop with `TASK_DEPENDENCY_VIOLATION`.

## Important Behavioral Contracts

- Schema management is through Alembic; application startup does not call `create_all()`.
- SQLite and application paths remain local and synchronous.
- Workflow database and LangGraph checkpoint versions must agree at pause/resume boundaries.
- Approval decisions are not recreated during clarification or retry recovery.
- Audit lifecycle events are idempotent.
- Task-level paths must reach `ControlledEditor`; policy checks are not based on a union of unrelated plan tasks.
- Free-text approval conditions are not interpreted as filesystem allowlists.
- Historical workflow data has not been manually mutated.

## Worktree State

The worktree is intentionally dirty and includes all fixes described above. Newly added files include:

- `app/orchestration/tasks.py`
- `migrations/versions/002_clarification_scope.py`
- `tests/integration/test_coding_task_selection.py`
- `tests/unit/test_coding_task_selection.py`
- `tests/unit/test_openai_provider.py`
- `tests/unit/test_openai_schema_compatibility.py`

See `CODEX_VERIFICATION_STATUS.md` for the detailed file map and commands.