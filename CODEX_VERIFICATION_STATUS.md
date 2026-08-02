# Codex Verification and Change Index

Updated: 2026-08-02

## Latest Successful Commands

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_coding_task_selection.py tests/integration/test_coding_task_selection.py -v
.venv\Scripts\python.exe -m pytest tests/integration/test_checkpoint_restart.py -v
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pytest -q
git diff --check
```

Results:

- Focused dependency-aware task-selection tests: 17 passed.
- Checkpoint restart tests: 2 passed.
- Full suite: 172 passed, 2 skipped.
- Ruff: all checks passed.
- Git whitespace validation: passed.
- OpenAI calls: none.

## File Map

### Agent Providers and Schemas

- `app/agents/openai_provider.py`: native structured output, local schema compatibility, sanitized failure diagnostics.
- `app/agents/runner.py`: sanitized agent execution failure persistence.
- `app/agents/design_agent.py`: Design Agent schema/provider integration.
- `app/agents/repository_coding_agent.py`: passes the selected `active_task` to Coding Agent.
- `app/agents/scripted_provider.py`: offline deterministic behavior, active-task mapping, scenario-compatible paths.
- `app/schemas/agents/design.py`: strict-output-compatible Design schema.
- `app/schemas/agents/coding.py`: strict Coding output and active-task input.
- `app/schemas/agents/planning.py`: planning schema compatibility adjustments.
- `app/schemas/agents/validation.py`: validation schema compatibility adjustments.
- `tests/unit/test_openai_provider.py`: provider behavior without network calls.
- `tests/unit/test_openai_schema_compatibility.py`: all agent output schemas build locally.

### Workflow Orchestration

- `app/orchestration/nodes.py`: clarification preparation/gate, Design retry handling, task satisfaction, dependency-aware selection, path evidence.
- `app/orchestration/graph.py`: clarification split and safe-stop routing for Coding selection failures.
- `app/orchestration/routing.py`: Design retry routing.
- `app/orchestration/state.py`: pending/task/retry state fields.
- `app/orchestration/tasks.py`: deterministic task completion, dependency readiness, selection, and executable plan filtering.
- `prompts/coding-agent.md`: Coding Agent must use the supplied active task and avoid completed design artifacts.

### Services and Repositories

- `app/services/workflow_service.py`: clarification validation/resume, controlled Design retry, legacy recovery audit lifecycle.
- `app/repositories/workflow_repository.py`: transactional clarification persistence, workflow-scoped lookup, task completion persistence.
- `app/repositories/audit_repository.py`: idempotent audit-event existence lookup.
- `app/api/v1/workflows.py`: controlled retry route.
- `app/core/exceptions.py`: sanitized internal details support.

### Database and Migration

- `app/database/models/workflow_requirement.py`: nullable `clarification_id` and composite uniqueness.
- `migrations/versions/002_clarification_scope.py`: column addition, legacy JSON backfill, unique constraint, reversible downgrade.
- `tests/integration/test_migrations.py`: migration cycle, constraint inspection, and legacy ID preservation.

### Path Policy and Editing

- `app/tools/path_policy.py`: normalized workspace-relative paths, task/scenario effective allowlists, global escape protection.
- `app/tools/controlled_editor.py`: explicit allowed-path enforcement and sanitized error details.
- `tests/unit/test_path_policy.py`: root paths, empty/non-empty scenarios, legacy notation, traversal and absolute blocking.
- `tests/unit/test_controlled_editor.py`: editor enforcement of task paths.
- `tests/integration/test_workflow_safe_stop.py`: safe-stop policy diagnostics.

### Integration Coverage

- `tests/integration/test_requirement_clarification_resume.py`: version agreement, stale/duplicate handling, cross-workflow isolation.
- `tests/integration/test_checkpoint_restart.py`: persisted approval and clarification resume.
- `tests/integration/test_workflow_retry.py`: Design retry success/exhaustion/restart/legacy recovery and audit idempotency.
- `tests/integration/test_coding_task_selection.py`: satisfied Design skip, setup-first selection, task allowlist propagation, dependency-deadlock safe stop.

## Current Test Invariants

- Two workflows may independently use `CLR-1-2` without reading or mutating each other.
- Repeated clarification submission creates no duplicate answers or audit events.
- Legacy Design retry emits exactly one `RETRY_STARTED` and one `AGENT_RETRY_RECOVERED`.
- Requirement approval remains exactly one decision across Design retries.
- Root-level approved paths are accepted.
- Empty generic scenario paths do not deny task paths.
- Non-empty scenario paths restrict task paths.
- Absolute, traversal, symlink, and workspace escapes remain blocked.
- Completed Design tasks remain in the plan but are not coded again.
- Setup tasks run before dependent implementation tasks.
- Dependency-blocked tasks are never selected.
- Selection order is deterministic.

## Operational Notes

- Run `alembic upgrade head` before using an existing persistent application database with this worktree.
- Do not manually update historical SQLite rows or checkpoint records.
- Existing historical safe-stopped workflows are evidence; create or controlled-resume workflows only through supported APIs.
- The `.env` file was intentionally not inspected or modified.
- Line-ending warnings on Windows are informational; `git diff --check` passes.