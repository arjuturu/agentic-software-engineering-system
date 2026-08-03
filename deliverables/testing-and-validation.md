# Testing and Validation

## Validation layers

| Layer | Deterministic evidence |
| --- | --- |
| Structured output | Pydantic Agent output models; provider schema-compatibility tests build strict schemas offline |
| Scenario resolution | Strong URL-shortener evidence and explicit Greenfield/Brownfield/Ambiguous profiles |
| Planning | PlanValidator checks task IDs, execution order, dependencies, task types, paths, governance duplication, and required lifecycle tasks |
| Task sequencing | first_executable_task selects dependency-ready unfinished tasks in approved order |
| Path ownership | Scenario restrictions plus explicit task allowlists; absolute/traversal/symlink/workspace escapes blocked |
| Edit concurrency | CREATE expected-absent rule; MODIFY SHA-256 precondition; exact targeted replacement cardinality |
| Controlled execution | ControlledEditor validates a whole batch and restores earlier writes after later failures |
| Repository safety | Bounded read-only scan, restricted files, no source execution, governed source copy |
| Git | Local-only repository, explicit staging, baseline/working branches, no remote operations |
| Task validation | Current task commands run before completion; corrections remain owned by their originating task |
| Final completeness | all_required_tasks_completed guards final validation/release |
| Application contract | Isolated import and OpenAPI checks, scenario route/method expectations, control-plane independence |
| Persistence | Alembic upgrade/downgrade/re-upgrade; no startup create_all |
| Quality | Generated and platform Pytest, Ruff, Git status, checkpoint restart tests |
| Source immutability | Copy exclusions and hash/Git-status evidence; Brownfield tests compare source before/after |

Intermediate tasks are validated according to their ownership and current completeness. Missing
future endpoints during an early task are not treated as a final application state. Final validation
evaluates every approved acceptance criterion only after all executable tasks are completed or
satisfied.

## Scenario validation evidence

- Greenfield: evidence/04-greenfield-runtime contains Alembic, Pytest, Ruff, baseline Git status,
  commit, and source hashes.
- Brownfield: generated artifacts contain scan, impact, migration, validation, and release evidence;
  integration tests validate analytics and source immutability. Dedicated evidence/05 runtime
  exports remain missing.
- Ambiguous: evidence/06-ambiguous-runtime contains Pytest and Ruff output; the transcript and
  workflow artifacts demonstrate clarification and alias validation.
- Platform: tests cover health, migrations, approvals, checkpoint restart, retries, rollback,
  safe stop, path policy, ControlledEditor, task selection, scenario workflows, and reporting.

## Engineering-quality matrix

| Attribute | Implementation evidence | Validation evidence |
| --- | --- | --- |
| Modularity | API, agents, orchestration, tools, repositories, services | Unit tests by component |
| Separation of concerns | Model proposes; routing/tools decide | Agent runner and routing tests |
| Schema safety | Strict Pydantic outputs and OpenAI JSON schema | Schema compatibility tests |
| Migration discipline | Alembic-only schema management | Repeated migration cycle tests |
| Unit testing | Tools, policy, planning, providers, metrics | tests/unit |
| Integration testing | Stateful workflow and generated targets | tests/integration |
| Error handling | Safe error envelope and sanitized agent diagnostics | API/failure tests |
| Maintainability | Typed models and canonical task enum | Ruff E/F/I/B/UP |
| Auditability | IDs, versions, audit events, artifacts | Audit and report tests |
| Recoverability | Retry, replan, checkpoint, rollback, safe stop | Restart/retry/rollback tests |
| Source immutability | Governed copy and excluded metadata | Brownfield scenario tests/hashes |
| Secure boundaries | PathPolicy, hashes, allowlisted commands | Policy/editor tests |
| Scalability awareness | Separate metadata/checkpoints and services | Architecture review |

## Phase 6 verification

The final command set is:

~~~powershell
python -m pytest -q
python -m ruff check app tests scripts
git diff --check
~~~

Phase 6 result on Windows:

~~~text
259 passed, 3 skipped in 305.32s
~~~

The three skips are the expected symbolic-link limitations in PathPolicy, RepositoryScanner, and
WorkspaceManager tests. No application/orchestration behavior changed during Phase 6.
