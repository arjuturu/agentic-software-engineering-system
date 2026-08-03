import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.models import AuditEvent, WorkflowRequirement, WorkflowRun


def test_report_cli_reads_persisted_records_without_mutation(tmp_path: Path) -> None:
    database = tmp_path / "report.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    Base.metadata.create_all(engine)
    started = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)
    with Session(engine) as session:
        for workflow_id, status, seconds, profile, scenario_type in (
            (
                "WF-REPORT-READY",
                "READY",
                20,
                "URL_SHORTENER_GREENFIELD",
                "GREENFIELD",
            ),
            ("WF-REPORT-FAILED", "FAILED", 40, "GENERIC", "GREENFIELD"),
        ):
            session.add(
                WorkflowRun(
                    id=workflow_id,
                    thread_id=f"TH-{workflow_id}",
                    correlation_id=f"COR-{workflow_id}",
                    scenario_type=scenario_type,
                    repository_path="not-exported",
                    status=status,
                    current_stage="COMPLETE",
                    state_version=1,
                    started_at=started,
                    updated_at=started + timedelta(seconds=seconds),
                    completed_at=started + timedelta(seconds=seconds),
                )
            )
            session.flush()
            session.add(
                WorkflowRequirement(
                    workflow_id=workflow_id,
                    version=1,
                    original_requirement="isolated fixture",
                    status="APPROVED",
                )
            )
            session.add(
                AuditEvent(
                    workflow_id=workflow_id,
                    event_type="WORKFLOW_CREATED",
                    stage="CREATED",
                    actor_type="SYSTEM",
                    details_json={
                        "scenario_type": scenario_type,
                        "scenario_profile": profile,
                    },
                    occurred_at=started,
                )
            )
        session.add(
            AuditEvent(
                workflow_id="WF-REPORT-READY",
                event_type="APPROVAL_DECIDED",
                stage="REQUIREMENT",
                actor_type="HUMAN",
                occurred_at=started + timedelta(seconds=5),
            )
        )
        session.commit()
        before_workflows = list(
            session.execute(
                select(
                    WorkflowRun.id,
                    WorkflowRun.status,
                    WorkflowRun.current_stage,
                    WorkflowRun.state_version,
                    WorkflowRun.updated_at,
                ).order_by(WorkflowRun.id)
            )
        )
        before_events = list(
            session.execute(
                select(
                    AuditEvent.id,
                    AuditEvent.event_type,
                    AuditEvent.stage,
                    AuditEvent.details_json,
                    AuditEvent.occurred_at,
                ).order_by(AuditEvent.id)
            )
        )

    output_json = tmp_path / "evidence" / "reliability.json"
    output_markdown = tmp_path / "docs" / "reliability.md"
    environment = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{database.as_posix()}",
        "LLM_MODE": "SCRIPTED",
    }
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/generate_reliability_report.py",
            "--output-json",
            str(output_json),
            "--output-markdown",
            str(output_markdown),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        capture_output=True,
        text=True,
        shell=False,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["summary"]["total_workflows"] == 2
    assert payload["summary"]["ready_workflows"] == 1
    assert payload["summary"]["failed_workflows"] == 1
    assert payload["summary"]["success_rate_percent"] == 50.0
    assert payload["duration_metrics"]["average_duration_seconds"] == 30.0
    assert payload["interaction_metrics"]["approval_event_count"] == 1
    assert "WF-REPORT-READY" in output_markdown.read_text(encoding="utf-8")
    assert "not-exported" not in output_json.read_text(encoding="utf-8")

    with Session(engine) as session:
        after_workflows = list(
            session.execute(
                select(
                    WorkflowRun.id,
                    WorkflowRun.status,
                    WorkflowRun.current_stage,
                    WorkflowRun.state_version,
                    WorkflowRun.updated_at,
                ).order_by(WorkflowRun.id)
            )
        )
        after_events = list(
            session.execute(
                select(
                    AuditEvent.id,
                    AuditEvent.event_type,
                    AuditEvent.stage,
                    AuditEvent.details_json,
                    AuditEvent.occurred_at,
                ).order_by(AuditEvent.id)
            )
        )
        assert after_workflows == before_workflows
        assert after_events == before_events
    engine.dispose()
