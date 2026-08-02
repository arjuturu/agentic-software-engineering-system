"""Create the Phase 1 application schema.

Revision ID: 001_initial_schema
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "short_urls",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("short_code", sa.String(64), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), server_default="ACTIVE", nullable=False),
        sa.Column("source_type", sa.String(30), server_default="MANUAL", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("click_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("click_count >= 0", name="click_count_nonnegative"),
        sa.PrimaryKeyConstraint("id", name="pk_short_urls"),
        sa.UniqueConstraint("short_code", name="uq_short_urls_short_code"),
    )
    op.create_index("ix_short_urls_short_code", "short_urls", ["short_code"], unique=False)

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("thread_id", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("scenario_type", sa.String(30), nullable=False),
        sa.Column("repository_path", sa.Text(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("current_stage", sa.String(80), nullable=False),
        sa.Column("state_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("original_branch", sa.String(255), nullable=True),
        sa.Column("baseline_commit", sa.String(64), nullable=True),
        sa.Column("working_branch", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("state_version >= 1", name="state_version_positive"),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_runs"),
        sa.UniqueConstraint("thread_id", name="uq_workflow_runs_thread_id"),
    )
    op.create_index(
        "ix_workflow_runs_correlation_id", "workflow_runs", ["correlation_id"], unique=False
    )

    op.create_table(
        "url_access_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("short_url_id", sa.String(36), nullable=False),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("referrer", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["short_url_id"],
            ["short_urls.id"],
            name="fk_url_access_events_short_url_id_short_urls",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_url_access_events"),
    )
    op.create_index(
        "ix_url_access_events_short_url_id", "url_access_events", ["short_url_id"], unique=False
    )
    op.create_index(
        "ix_url_access_events_accessed_at", "url_access_events", ["accessed_at"], unique=False
    )

    op.create_table(
        "workflow_requirements",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("workflow_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("original_requirement", sa.Text(), nullable=False),
        sa.Column("normalized_requirement", sa.Text(), nullable=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("analysis_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name="fk_workflow_requirements_workflow_id_workflow_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_requirements"),
        sa.UniqueConstraint(
            "workflow_id",
            "version",
            name="uq_workflow_requirements_workflow_version",
        ),
    )

    op.create_table(
        "workflow_tasks",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("workflow_id", sa.String(36), nullable=False),
        sa.Column("task_key", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("task_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column(
            "dependencies_json", sa.JSON(), server_default=sa.text("'[]'"), nullable=False
        ),
        sa.Column(
            "expected_files_json", sa.JSON(), server_default=sa.text("'[]'"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name="fk_workflow_tasks_workflow_id_workflow_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_tasks"),
        sa.UniqueConstraint(
            "workflow_id", "task_key", name="uq_workflow_tasks_workflow_task_key"
        ),
    )

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("workflow_id", sa.String(36), nullable=False),
        sa.Column("gate_type", sa.String(50), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), server_default="PENDING", nullable=False),
        sa.Column("allowed_actions_json", sa.JSON(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name="fk_approval_requests_workflow_id_workflow_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_approval_requests"),
    )
    op.create_index(
        "ix_approval_requests_workflow_id_status",
        "approval_requests",
        ["workflow_id", "status"],
        unique=False,
    )

    op.create_table(
        "agent_executions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("workflow_id", sa.String(36), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("stage", sa.String(100), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("attempt_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("input_artifact", sa.Text(), nullable=True),
        sa.Column("output_artifact", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "attempt_number >= 1", name="attempt_number_positive"
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name="fk_agent_executions_workflow_id_workflow_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_executions"),
    )
    op.create_index(
        "ix_agent_executions_workflow_id_agent_name",
        "agent_executions",
        ["workflow_id", "agent_name"],
        unique=False,
    )

    op.create_table(
        "workflow_artifacts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("workflow_id", sa.String(36), nullable=False),
        sa.Column("artifact_type", sa.String(80), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(30), server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name="fk_workflow_artifacts_workflow_id_workflow_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_artifacts"),
        sa.UniqueConstraint(
            "workflow_id",
            "artifact_type",
            "version",
            name="uq_workflow_artifacts_workflow_type_version",
        ),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("workflow_id", sa.String(36), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("stage", sa.String(100), nullable=True),
        sa.Column("actor_type", sa.String(40), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name="fk_audit_events_workflow_id_workflow_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index(
        "ix_audit_events_workflow_id_occurred_at",
        "audit_events",
        ["workflow_id", "occurred_at"],
        unique=False,
    )
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"], unique=False)

    op.create_table(
        "approval_decisions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("approval_id", sa.String(36), nullable=False),
        sa.Column("workflow_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column(
            "conditions_json", sa.JSON(), server_default=sa.text("'[]'"), nullable=False
        ),
        sa.Column("decided_by", sa.String(255), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["approval_id"],
            ["approval_requests.id"],
            name="fk_approval_decisions_approval_id_approval_requests",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name="fk_approval_decisions_workflow_id_workflow_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_approval_decisions"),
        sa.UniqueConstraint("approval_id", name="uq_approval_decisions_approval_id"),
    )


def downgrade() -> None:
    op.drop_table("approval_decisions")
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_index("ix_audit_events_workflow_id_occurred_at", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("workflow_artifacts")
    op.drop_index(
        "ix_agent_executions_workflow_id_agent_name", table_name="agent_executions"
    )
    op.drop_table("agent_executions")
    op.drop_index(
        "ix_approval_requests_workflow_id_status", table_name="approval_requests"
    )
    op.drop_table("approval_requests")
    op.drop_table("workflow_tasks")
    op.drop_table("workflow_requirements")
    op.drop_index("ix_url_access_events_accessed_at", table_name="url_access_events")
    op.drop_index("ix_url_access_events_short_url_id", table_name="url_access_events")
    op.drop_table("url_access_events")
    op.drop_index("ix_workflow_runs_correlation_id", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    op.drop_index("ix_short_urls_short_code", table_name="short_urls")
    op.drop_table("short_urls")

