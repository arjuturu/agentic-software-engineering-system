from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.models import AuditEvent, WorkflowRequirement, WorkflowRun
from app.schemas.reliability import ReliabilityFilters
from app.services.reliability_metrics import (
    ReliabilityMetricsService,
    render_markdown,
    serialize_report,
)

NOW = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as active:
        yield active
    engine.dispose()


def add_workflow(
    session: Session,
    workflow_id: str,
    status: str,
    *,
    scenario_type: str = "GREENFIELD",
    seconds: int | None = 10,
    stage: str = "COMPLETE",
    profile: str = "GENERIC",
) -> WorkflowRun:
    row = WorkflowRun(
        id=workflow_id,
        thread_id=f"TH-{workflow_id}",
        correlation_id=f"COR-{workflow_id}",
        scenario_type=scenario_type,
        repository_path="fixture",
        status=status,
        current_stage=stage,
        state_version=1,
        started_at=NOW,
        updated_at=NOW,
        completed_at=NOW + timedelta(seconds=seconds) if seconds is not None else None,
    )
    session.add(row)
    session.flush()
    add_event(
        session,
        workflow_id,
        "WORKFLOW_CREATED",
        "CREATED",
        {"scenario_type": scenario_type, "scenario_profile": profile},
    )
    session.add(
        WorkflowRequirement(
            workflow_id=workflow_id,
            version=1,
            original_requirement="fixture",
            status="APPROVED",
        )
    )
    session.flush()
    return row


def add_event(
    session: Session,
    workflow_id: str,
    event_type: str,
    stage: str,
    details: dict | None = None,
) -> None:
    session.add(
        AuditEvent(
            workflow_id=workflow_id,
            event_type=event_type,
            stage=stage,
            actor_type="SYSTEM",
            details_json=details,
            occurred_at=NOW,
        )
    )
    session.flush()


def report(session: Session, filters: ReliabilityFilters | None = None):
    return ReliabilityMetricsService(session).build_report(filters, generated_at=NOW)


def test_empty_workflow_set_reports_zero_and_null_durations(session: Session) -> None:
    result = report(session)

    assert result.summary.total_workflows == 0
    assert result.summary.success_rate_percent == 0.0
    assert result.duration_metrics.average_duration_seconds is None
    assert result.interaction_metrics.average_approval_count_per_workflow is None


def test_one_ready_workflow_calculates_duration_and_success(session: Session) -> None:
    add_workflow(session, "WF-READY", "READY", seconds=12)

    result = report(session)

    assert result.summary.ready_workflows == 1
    assert result.summary.success_rate_percent == 100.0
    assert result.duration_metrics.average_duration_seconds == 12.0
    assert result.duration_metrics.minimum_duration_seconds == 12.0
    assert result.duration_metrics.maximum_duration_seconds == 12.0
    assert result.duration_metrics.average_time_to_ready_seconds == 12.0


def test_mixed_outcomes_and_incomplete_duration_exclusion(session: Session) -> None:
    add_workflow(session, "WF-READY", "READY", seconds=10)
    add_workflow(session, "WF-NOT-READY", "NOT_READY", seconds=20)
    add_workflow(session, "WF-INCOMPLETE", "RUNNING", seconds=None)
    add_workflow(session, "WF-FAILED", "FAILED", seconds=30)
    add_workflow(session, "WF-CANCELLED", "CANCELLED", seconds=40)

    result = report(session)

    assert result.summary.model_dump() == {
        "total_workflows": 5,
        "ready_workflows": 1,
        "not_ready_workflows": 1,
        "failed_workflows": 1,
        "cancelled_workflows": 1,
        "rollback_complete_workflows": 0,
        "success_rate_percent": 20.0,
    }
    assert result.duration_metrics.average_duration_seconds == 25.0
    assert result.duration_metrics.average_time_to_failure_seconds == 30.0
    assert result.workflows[2].duration_seconds is None


def test_retry_aggregation_uses_authoritative_audit_events(session: Session) -> None:
    add_workflow(session, "WF-RETRY", "READY")
    add_event(session, "WF-RETRY", "PLAN_CORRECTION_STARTED", "PLANNING")
    add_event(session, "WF-RETRY", "RETRY_STARTED", "CODING")
    add_event(session, "WF-RETRY", "RETRY_STARTED", "DESIGN")

    result = report(session)

    assert result.workflows[0].planning_retries == 1
    assert result.workflows[0].coding_retries == 1
    assert result.reliability_metrics.planning_retry_count == 1
    assert result.reliability_metrics.coding_retry_count == 1
    assert result.reliability_metrics.total_retry_count == 3


def test_approval_and_clarification_event_classification(session: Session) -> None:
    add_workflow(session, "WF-INTERACTION", "READY")
    for gate in ("REQUIREMENT", "ARCHITECTURE_AND_PLAN", "HIGH_RISK_CHANGE", "RELEASE"):
        add_event(session, "WF-INTERACTION", "APPROVAL_DECIDED", gate)
    add_event(session, "WF-INTERACTION", "CLARIFICATION_REQUESTED", "CLARIFICATION")
    add_event(session, "WF-INTERACTION", "CLARIFICATION_SUBMITTED", "CLARIFICATION")

    result = report(session)
    metrics = result.interaction_metrics

    assert metrics.approval_event_count == 4
    assert metrics.requirement_approval_count == 1
    assert metrics.architecture_plan_approval_count == 1
    assert metrics.high_risk_approval_count == 1
    assert metrics.release_approval_count == 1
    assert metrics.clarification_workflow_count == 1
    assert metrics.clarification_event_count == 1


def test_rollback_and_safe_stop_classification_are_explicit(session: Session) -> None:
    add_workflow(session, "WF-ROLLBACK", "NOT_READY", stage="ROLLBACK_COMPLETE")
    add_event(session, "WF-ROLLBACK", "ROLLBACK_STARTED", "ROLLBACK")
    add_event(session, "WF-ROLLBACK", "ROLLBACK_COMPLETED", "ROLLBACK", {"success": True})
    add_workflow(session, "WF-SAFE", "SAFE_STOPPED", stage="SAFE_STOP")
    add_event(session, "WF-SAFE", "SAFE_STOP_TRIGGERED", "SAFE_STOP")

    result = report(session)

    assert result.summary.rollback_complete_workflows == 1
    assert result.reliability_metrics.rollback_triggered_count == 1
    assert result.reliability_metrics.safe_stop_count == 1
    assert result.workflows[0].rollback_status == "COMPLETED"


def test_unsupported_metrics_are_null_and_explained(session: Session) -> None:
    add_workflow(session, "WF-NULL", "FAILED")

    result = report(session)

    assert result.duration_metrics.failure_to_resolution_seconds is None
    assert result.workflows[0].provider is None
    assert result.workflows[0].final_release_status is None
    assert set(result.unsupported_metrics) == {
        "failure_to_resolution_seconds",
        "provider",
        "final_release_status",
    }


def test_filter_behavior(session: Session) -> None:
    add_workflow(
        session,
        "WF-GREEN",
        "READY",
        profile="URL_SHORTENER_GREENFIELD",
    )
    add_workflow(
        session,
        "WF-BROWN",
        "READY",
        scenario_type="BROWNFIELD",
        profile="URL_SHORTENER_BROWNFIELD",
    )

    by_type = report(session, ReliabilityFilters(scenario_type="BROWNFIELD"))
    by_profile = report(
        session,
        ReliabilityFilters(scenario_profile="URL_SHORTENER_GREENFIELD"),
    )
    by_id = report(session, ReliabilityFilters(workflow_id="WF-GREEN"))

    assert [item.workflow_id for item in by_type.workflows] == ["WF-BROWN"]
    assert [item.workflow_id for item in by_profile.workflows] == ["WF-GREEN"]
    assert [item.workflow_id for item in by_id.workflows] == ["WF-GREEN"]
    with pytest.raises(ValueError, match="Provider filtering is unavailable"):
        report(session, ReliabilityFilters(provider="SCRIPTED"))


def test_json_serialization_is_stable_and_sanitized(session: Session) -> None:
    add_workflow(session, "WF-STABLE", "READY")
    result = report(session)

    first = serialize_report(result)
    second = serialize_report(result)

    assert first == second
    assert '"workflow_id": "WF-STABLE"' in first
    assert "repository_path" not in first
    assert "correlation_id" not in first


def test_markdown_generation_contains_required_sections(session: Session) -> None:
    add_workflow(session, "WF-MARKDOWN", "READY")

    markdown = render_markdown(report(session))

    assert "# Reliability Metrics" in markdown
    assert "## Report metadata" in markdown
    assert "## Executive summary" in markdown
    assert "## Workflow outcomes" in markdown
    assert "## Metric definitions and sources" in markdown
    assert "## Reliability interpretation" in markdown
    assert "## Limitations" in markdown


def test_profile_candidates_do_not_overstate_scripted_benchmark(session: Session) -> None:
    add_workflow(
        session,
        "WF-CANDIDATE",
        "READY",
        profile="URL_SHORTENER_GREENFIELD",
    )

    result = report(session)

    assert result.scripted_benchmark.complete is False
    assert result.scripted_benchmark.scenarios[0].scenario == (
        "URL_SHORTENER_GREENFIELD_HAPPY_PATH"
    )
    assert "profile-matched candidates" in render_markdown(result)
