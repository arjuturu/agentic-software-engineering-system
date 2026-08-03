# Reliability Metrics

## Report metadata

- Generated: 2026-08-03T14:38:19.629471Z
- Filters: {"provider": null, "scenario_profile": null, "scenario_type": null, "workflow_id": null}
- Data source: SQLAlchemy workflow, audit, requirement, and artifact records
- Workflows included: 5

## Executive summary

| Metric | Value |
| --- | ---: |
| Total workflows | 5 |
| Ready workflows | 4 |
| Not-ready workflows | 0 |
| Failed workflows | 0 |
| Cancelled workflows | 0 |
| Rollback-complete workflows | 0 |
| Success rate | 80.00% |
| Average duration (seconds) | 243.563 |
| Clarification events | 1 |
| Approval events | 12 |
| Planning retries | 0 |
| Coding retries | 0 |
| Rollback triggered | 0 |
| Safe stops | 0 |

## Workflow outcomes

| Workflow | Scenario | Status | Duration | Retries | Clarifications | Approvals | Rollback |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| WF-7989E1418EA9 | URL_SHORTENER_GREENFIELD | READY | 119.638s | 0 | 0 | 3 | NOT_TRIGGERED |
| WF-9D68C26C57A2 | URL_SHORTENER_BROWNFIELD | READY | 193.530s | 0 | 0 | 3 | NOT_TRIGGERED |
| WF-6D6C54D2DAD9 | URL_SHORTENER_BROWNFIELD | READY | 386.768s | 0 | 0 | 3 | NOT_TRIGGERED |
| WF-95C6190BCF43 | URL_SHORTENER_AMBIGUOUS_ALIASES | WAITING_FOR_CLARIFICATION | — | 0 | 0 | 0 | NOT_TRIGGERED |
| WF-A73E0C8C31C4 | URL_SHORTENER_AMBIGUOUS_ALIASES | READY | 274.317s | 0 | 1 | 3 | NOT_TRIGGERED |

## Scripted benchmark

The benchmark is incomplete: rows below are profile-matched candidates because exact scripted scenario and provider mode are not durably persisted.

| Scenario | Workflow | Status | Clarification observed | Topology | Retries | Rollback |
| --- | --- | --- | --- | --- | ---: | --- |
| URL_SHORTENER_GREENFIELD_HAPPY_PATH | WF-7989E1418EA9 | READY | No | NEW_WORKSPACE | 0 | NOT_TRIGGERED |
| URL_SHORTENER_BROWNFIELD_ANALYTICS | WF-6D6C54D2DAD9 | READY | No | SOURCE_COPY | 0 | NOT_TRIGGERED |
| URL_SHORTENER_AMBIGUOUS_ALIASES | WF-A73E0C8C31C4 | READY | Yes | SOURCE_COPY | 0 | NOT_TRIGGERED |

## Metric definitions and sources

- A successful workflow has canonical status READY; artifacts alone never imply success.
- Outcome counts use exact persisted workflow status values. Rollback completion also requires a completed rollback event or the canonical rollback-complete stage.
- Duration is completed_at minus started_at. Incomplete workflows are excluded.
- Approval counts use accepted APPROVAL_DECIDED audit events, classified by gate stage.
- Clarification counts use accepted CLARIFICATION_SUBMITTED audit events.
- Planning retries use PLAN_CORRECTION_STARTED (or a planning RETRY_STARTED event); coding retries use CODING-stage RETRY_STARTED events.
- Total retries count RETRY_STARTED and PLAN_CORRECTION_STARTED lifecycle events once.
- Rollback and safe-stop counts require their explicit audit event or canonical state.

## Reliability interpretation

These results measure the persisted workflows selected by the report filters. A fully READY scripted benchmark demonstrates deterministic reliability for that benchmark; it does not prove production reliability under arbitrary requirements or model outputs.

The interactive evidence database contains five persisted records because the Brownfield scenario
was executed more than once and one Ambiguous workflow was preserved at the clarification
boundary. Across all records, four reached READY and one remained
WAITING_FOR_CLARIFICATION, producing an aggregate READY rate of 80%.

The selected assignment candidates are Greenfield WF-7989E1418EA9, Brownfield
WF-6D6C54D2DAD9, and completed Ambiguous WF-A73E0C8C31C4; all reached READY. Additional
Brownfield WF-9D68C26C57A2 also reached READY. Ambiguous WF-95C6190BCF43 is incomplete at a
human clarification interrupt, not failed. The completed Ambiguous candidate proves a real
clarification pause and successful resume.

This is interactive development/demonstration evidence, not a statistically meaningful production
benchmark or a clean three-workflow run. Exact provider and scripted-scenario identity are not
durably persisted, so candidate mapping is profile-based.

MTTR is not currently measurable because the persistence model does not store a canonical
incident-start and resolution-completion timestamp pair. Workflow duration, time to READY/time to
failure when available, retry, rollback, and safe-stop counts are reported without relabeling them
as MTTR.

## Limitations

- Scripted mode uses deterministic model responses.
- Small sample sizes are not statistically meaningful.
- Live model behavior is variable.
- Incomplete workflows are excluded from completed-duration averages.
- Unavailable metrics are reported as null.
- Database history may include development and test runs unless filters are used.
