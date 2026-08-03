import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.database.models import AuditEvent, WorkflowArtifact, WorkflowRequirement, WorkflowRun
from app.schemas.reliability import (
    AggregateReliabilityMetrics,
    DurationMetrics,
    InteractionMetrics,
    ReliabilityFilters,
    ReliabilityReport,
    ReliabilitySummary,
    ScriptedBenchmark,
    ScriptedBenchmarkScenario,
    WorkflowReliabilityDetail,
)

_FAILURE_STATUSES = {"FAILED", "NOT_READY", "CANCELLED", "SAFE_STOPPED"}
_BENCHMARK_PROFILES = {
    "URL_SHORTENER_GREENFIELD": "URL_SHORTENER_GREENFIELD_HAPPY_PATH",
    "URL_SHORTENER_BROWNFIELD": "URL_SHORTENER_BROWNFIELD_ANALYTICS",
    "URL_SHORTENER_AMBIGUOUS_ALIASES": "URL_SHORTENER_AMBIGUOUS_ALIASES",
}


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _seconds(started_at: datetime, completed_at: datetime | None) -> float | None:
    if completed_at is None:
        return None
    return round((_utc(completed_at) - _utc(started_at)).total_seconds(), 3)


def _average(values: Iterable[float]) -> float | None:
    items = list(values)
    return round(mean(items), 3) if items else None


class ReliabilityMetricsService:
    """Build read-only reliability evidence from canonical application records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def build_report(
        self,
        filters: ReliabilityFilters | None = None,
        *,
        generated_at: datetime | None = None,
    ) -> ReliabilityReport:
        active_filters = filters or ReliabilityFilters()
        rows = self._workflow_rows(active_filters)
        events = self._events([row.id for row in rows])
        profiles = self._scenario_profiles(events)
        if active_filters.scenario_profile:
            rows = [
                row
                for row in rows
                if profiles.get(row.id) == active_filters.scenario_profile
            ]

        workflow_ids = [row.id for row in rows]
        events_by_workflow: dict[str, list[AuditEvent]] = defaultdict(list)
        for event in events:
            if event.workflow_id in workflow_ids:
                events_by_workflow[event.workflow_id].append(event)
        details = [
            self._workflow_detail(row, profiles.get(row.id), events_by_workflow[row.id])
            for row in rows
        ]
        all_events = [
            event for workflow_id in workflow_ids for event in events_by_workflow[workflow_id]
        ]
        summary = self._summary(details)
        durations = [item.duration_seconds for item in details if item.duration_seconds is not None]
        ready_durations = [
            item.duration_seconds
            for item in details
            if item.status == "READY" and item.duration_seconds is not None
        ]
        failure_durations = [
            item.duration_seconds
            for item in details
            if item.status in _FAILURE_STATUSES and item.duration_seconds is not None
        ]
        return ReliabilityReport(
            generated_at=_utc(generated_at or utc_now()),
            filters=active_filters,
            data_source="SQLAlchemy workflow, audit, requirement, and artifact records",
            summary=summary,
            duration_metrics=DurationMetrics(
                average_duration_seconds=_average(durations),
                minimum_duration_seconds=round(min(durations), 3) if durations else None,
                maximum_duration_seconds=round(max(durations), 3) if durations else None,
                average_time_to_ready_seconds=_average(ready_durations),
                average_time_to_failure_seconds=_average(failure_durations),
                failure_to_resolution_seconds=None,
            ),
            interaction_metrics=self._interaction_metrics(details, all_events),
            reliability_metrics=self._reliability_metrics(details, all_events),
            scripted_benchmark=self._benchmark(details, events_by_workflow),
            unsupported_metrics={
                "failure_to_resolution_seconds": (
                    "No canonical failure-resolution timestamp pair is persisted."
                ),
                "provider": (
                    "Execution mode is checkpoint state and is not persisted in "
                    "workflow/audit rows."
                ),
                "final_release_status": (
                    "This value is checkpoint state and is not persisted separately from status."
                ),
            },
            workflows=details,
        )

    def _workflow_rows(self, filters: ReliabilityFilters) -> list[WorkflowRun]:
        if filters.provider is not None:
            raise ValueError(
                "Provider filtering is unavailable because provider mode is not persisted."
            )
        statement = select(WorkflowRun)
        if filters.workflow_id:
            statement = statement.where(WorkflowRun.id == filters.workflow_id)
        if filters.scenario_type:
            statement = statement.where(WorkflowRun.scenario_type == filters.scenario_type)
        return list(
            self.session.scalars(statement.order_by(WorkflowRun.started_at, WorkflowRun.id))
        )

    def _events(self, workflow_ids: list[str]) -> list[AuditEvent]:
        if not workflow_ids:
            return []
        return list(
            self.session.scalars(
                select(AuditEvent)
                .where(AuditEvent.workflow_id.in_(workflow_ids))
                .order_by(AuditEvent.occurred_at, AuditEvent.id)
            )
        )

    @staticmethod
    def _scenario_profiles(events: list[AuditEvent]) -> dict[str, str]:
        profiles: dict[str, str] = {}
        for event in events:
            details = event.details_json or {}
            profile = details.get("scenario_profile")
            if (
                event.event_type == "WORKFLOW_CREATED"
                and event.workflow_id
                and isinstance(profile, str)
            ):
                profiles[event.workflow_id] = profile
        return profiles

    def _workflow_detail(
        self, row: WorkflowRun, profile: str | None, events: list[AuditEvent]
    ) -> WorkflowReliabilityDetail:
        counts = Counter(event.event_type for event in events)
        planning_retries = sum(
            event.event_type == "PLAN_CORRECTION_STARTED"
            or (event.event_type == "RETRY_STARTED" and event.stage == "PLANNING")
            for event in events
        )
        coding_retries = sum(
            event.event_type == "RETRY_STARTED" and event.stage == "CODING"
            for event in events
        )
        return WorkflowReliabilityDetail(
            workflow_id=row.id,
            scenario_type=row.scenario_type,
            scenario_profile=profile,
            status=row.status,
            started_at=_utc(row.started_at),
            completed_at=_utc(row.completed_at) if row.completed_at else None,
            duration_seconds=_seconds(row.started_at, row.completed_at),
            requirement_version=self._requirement_version(row.id),
            architecture_version=self._artifact_version(row.id, "DESIGN_AGENT_MARKDOWN"),
            plan_version=self._artifact_version(row.id, "PLANNING_AGENT_MARKDOWN"),
            planning_retries=planning_retries,
            coding_retries=coding_retries,
            clarification_count=counts["CLARIFICATION_SUBMITTED"],
            approval_count=counts["APPROVAL_DECIDED"],
            rollback_status=self._rollback_status(row, events),
            final_release_status=None,
        )

    def _requirement_version(self, workflow_id: str) -> int:
        value = self.session.scalar(
            select(func.max(WorkflowRequirement.version)).where(
                WorkflowRequirement.workflow_id == workflow_id
            )
        )
        return int(value or 0)

    def _artifact_version(self, workflow_id: str, artifact_type: str) -> int:
        value = self.session.scalar(
            select(func.max(WorkflowArtifact.version)).where(
                WorkflowArtifact.workflow_id == workflow_id,
                WorkflowArtifact.artifact_type == artifact_type,
            )
        )
        return int(value or 0)

    @staticmethod
    def _rollback_status(row: WorkflowRun, events: list[AuditEvent]) -> str:
        completed = [event for event in events if event.event_type == "ROLLBACK_COMPLETED"]
        if completed:
            success = (completed[-1].details_json or {}).get("success")
            return "COMPLETED" if success is True else "FAILED"
        if any(event.event_type == "ROLLBACK_STARTED" for event in events):
            return "TRIGGERED"
        if row.current_stage == "ROLLBACK_COMPLETE" or row.status == "ROLLBACK_COMPLETE":
            return "COMPLETED"
        return "NOT_TRIGGERED"

    @staticmethod
    def _summary(details: list[WorkflowReliabilityDetail]) -> ReliabilitySummary:
        statuses = Counter(item.status for item in details)
        total = len(details)
        ready = statuses["READY"]
        return ReliabilitySummary(
            total_workflows=total,
            ready_workflows=ready,
            not_ready_workflows=statuses["NOT_READY"],
            failed_workflows=statuses["FAILED"],
            cancelled_workflows=statuses["CANCELLED"],
            rollback_complete_workflows=sum(
                item.rollback_status == "COMPLETED" for item in details
            ),
            success_rate_percent=round(ready / total * 100, 2) if total else 0.0,
        )

    @staticmethod
    def _interaction_metrics(
        details: list[WorkflowReliabilityDetail], events: list[AuditEvent]
    ) -> InteractionMetrics:
        approvals = [event for event in events if event.event_type == "APPROVAL_DECIDED"]
        clarifications = [
            event for event in events if event.event_type == "CLARIFICATION_SUBMITTED"
        ]
        gates = Counter(event.stage for event in approvals)
        total = len(details)
        return InteractionMetrics(
            clarification_workflow_count=sum(item.clarification_count > 0 for item in details),
            clarification_event_count=len(clarifications),
            approval_event_count=len(approvals),
            requirement_approval_count=gates["REQUIREMENT"],
            architecture_plan_approval_count=gates["ARCHITECTURE_AND_PLAN"],
            high_risk_approval_count=gates["HIGH_RISK_CHANGE"],
            release_approval_count=gates["RELEASE"],
            average_approval_count_per_workflow=(
                round(len(approvals) / total, 3) if total else None
            ),
            average_clarification_count_per_workflow=(
                round(len(clarifications) / total, 3) if total else None
            ),
        )

    @staticmethod
    def _reliability_metrics(
        details: list[WorkflowReliabilityDetail], events: list[AuditEvent]
    ) -> AggregateReliabilityMetrics:
        rollback_workflows = {
            event.workflow_id for event in events if event.event_type == "ROLLBACK_STARTED"
        }
        safe_stop_workflows = {
            event.workflow_id for event in events if event.event_type == "SAFE_STOP_TRIGGERED"
        }
        safe_stop_workflows.update(
            item.workflow_id for item in details if item.status == "SAFE_STOPPED"
        )
        return AggregateReliabilityMetrics(
            planning_retry_count=sum(item.planning_retries for item in details),
            coding_retry_count=sum(item.coding_retries for item in details),
            total_retry_count=sum(
                event.event_type in {"RETRY_STARTED", "PLAN_CORRECTION_STARTED"}
                for event in events
            ),
            rollback_triggered_count=len(rollback_workflows),
            safe_stop_count=len(safe_stop_workflows),
        )

    @staticmethod
    def _benchmark(
        details: list[WorkflowReliabilityDetail],
        events_by_workflow: dict[str, list[AuditEvent]],
    ) -> ScriptedBenchmark:
        latest: dict[str, WorkflowReliabilityDetail] = {}
        for detail in details:
            scenario = _BENCHMARK_PROFILES.get(detail.scenario_profile or "")
            if scenario:
                latest[scenario] = detail
        scenarios = []
        for scenario in _BENCHMARK_PROFILES.values():
            detail = latest.get(scenario)
            if detail is None:
                continue
            events = events_by_workflow.get(detail.workflow_id, [])
            scenarios.append(
                ScriptedBenchmarkScenario(
                    scenario=scenario,
                    workflow_id=detail.workflow_id,
                    status=detail.status,
                    initial_clarification_observed=any(
                        event.event_type == "CLARIFICATION_REQUESTED" for event in events
                    ),
                    source_workspace_topology=(
                        "NEW_WORKSPACE" if detail.scenario_type == "GREENFIELD" else "SOURCE_COPY"
                    ),
                    retry_count=sum(
                        event.event_type in {"RETRY_STARTED", "PLAN_CORRECTION_STARTED"}
                        for event in events
                    ),
                    rollback_status=detail.rollback_status,
                )
            )
        # Profile matches are useful evidence, but exact scripted scenario and provider mode are
        # checkpoint-only fields. Historical candidates cannot prove a complete scripted benchmark.
        return ScriptedBenchmark(complete=False, scenarios=scenarios)


def serialize_report(report: ReliabilityReport) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def write_report_files(
    report: ReliabilityReport,
    *,
    output_json: Path | None = None,
    output_markdown: Path | None = None,
) -> None:
    for path, content in (
        (output_json, serialize_report(report)),
        (output_markdown, render_markdown(report)),
    ):
        if path is None:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _display(value: object) -> str:
    return "null" if value is None else str(value)


def render_markdown(report: ReliabilityReport) -> str:
    summary = report.summary
    duration = report.duration_metrics
    interaction = report.interaction_metrics
    reliability = report.reliability_metrics
    metrics = [
        ("Total workflows", summary.total_workflows),
        ("Ready workflows", summary.ready_workflows),
        ("Not-ready workflows", summary.not_ready_workflows),
        ("Failed workflows", summary.failed_workflows),
        ("Cancelled workflows", summary.cancelled_workflows),
        ("Rollback-complete workflows", summary.rollback_complete_workflows),
        ("Success rate", f"{summary.success_rate_percent:.2f}%"),
        ("Average duration (seconds)", duration.average_duration_seconds),
        ("Clarification events", interaction.clarification_event_count),
        ("Approval events", interaction.approval_event_count),
        ("Planning retries", reliability.planning_retry_count),
        ("Coding retries", reliability.coding_retry_count),
        ("Rollback triggered", reliability.rollback_triggered_count),
        ("Safe stops", reliability.safe_stop_count),
    ]
    lines = [
        "# Reliability Metrics",
        "",
        "## Report metadata",
        "",
        f"- Generated: {report.generated_at.isoformat().replace('+00:00', 'Z')}",
        f"- Filters: {json.dumps(report.filters.model_dump(), sort_keys=True)}",
        f"- Data source: {report.data_source}",
        f"- Workflows included: {summary.total_workflows}",
        "",
        "## Executive summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        *[f"| {name} | {_display(value)} |" for name, value in metrics],
        "",
        "## Workflow outcomes",
        "",
        "| Workflow | Scenario | Status | Duration | Retries | Clarifications | "
        "Approvals | Rollback |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in report.workflows:
        retries = item.planning_retries + item.coding_retries
        duration_value = (
            f"{item.duration_seconds:.3f}s" if item.duration_seconds is not None else "—"
        )
        lines.append(
            f"| {item.workflow_id} | {item.scenario_profile or item.scenario_type} | "
            f"{item.status} | {duration_value} | {retries} | {item.clarification_count} | "
            f"{item.approval_count} | {item.rollback_status} |"
        )
    lines.extend(
        [
            "",
            "## Scripted benchmark",
            "",
            (
                "All three scripted URL-shortener scenarios were identified from durable evidence."
                if report.scripted_benchmark.complete
                else "The benchmark is incomplete: rows below are profile-matched candidates "
                "because exact scripted scenario and provider mode are not durably persisted."
            ),
            "",
            "| Scenario | Workflow | Status | Clarification observed | Topology | "
            "Retries | Rollback |",
            "| --- | --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for item in report.scripted_benchmark.scenarios:
        lines.append(
            f"| {item.scenario} | {item.workflow_id} | {item.status} | "
            f"{'Yes' if item.initial_clarification_observed else 'No'} | "
            f"{item.source_workspace_topology} | {item.retry_count} | {item.rollback_status} |"
        )
    lines.extend(
        [
            "",
            "## Metric definitions and sources",
            "",
            "- A successful workflow has canonical status READY; artifacts alone never imply "
            "success.",
            "- Outcome counts use exact persisted workflow status values. Rollback completion also "
            "requires a completed rollback event or the canonical rollback-complete stage.",
            "- Duration is completed_at minus started_at. Incomplete workflows are excluded.",
            "- Approval counts use accepted APPROVAL_DECIDED audit events, classified by gate "
            "stage.",
            "- Clarification counts use accepted CLARIFICATION_SUBMITTED audit events.",
            "- Planning retries use PLAN_CORRECTION_STARTED (or a planning RETRY_STARTED event); "
            "coding retries use CODING-stage RETRY_STARTED events.",
            "- Total retries count RETRY_STARTED and PLAN_CORRECTION_STARTED lifecycle events "
            "once.",
            "- Rollback and safe-stop counts require their explicit audit event or canonical "
            "state.",
            "",
            "## Reliability interpretation",
            "",
            "These results measure the persisted workflows selected by the report filters. A fully "
            "READY scripted benchmark demonstrates deterministic reliability for that benchmark; "
            "it does not prove production reliability under arbitrary requirements or model "
            "outputs.",
            "",
            "## Unavailable metrics",
            "",
            *[f"- {name}: {reason}" for name, reason in report.unsupported_metrics.items()],
            "",
            "## Limitations",
            "",
            "- Scripted mode uses deterministic model responses.",
            "- Small sample sizes are not statistically meaningful.",
            "- Live model behavior is variable.",
            "- Incomplete workflows are excluded from completed-duration averages.",
            "- Unavailable metrics are reported as null.",
            "- Database history may include development and test runs unless filters are used.",
            "",
        ]
    )
    return "\n".join(lines)
