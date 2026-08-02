"""Scope clarification identifiers by workflow.

Revision ID: 002_clarification_scope
Revises: 001_initial_schema
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_clarification_scope"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("workflow_requirements") as batch_op:
        batch_op.add_column(sa.Column("clarification_id", sa.String(64), nullable=True))

    requirements = sa.table(
        "workflow_requirements",
        sa.column("id", sa.String(36)),
        sa.column("analysis_json", sa.JSON()),
        sa.column("clarification_id", sa.String(64)),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(requirements.c.id, requirements.c.analysis_json)
    ).mappings()
    for row in rows:
        analysis = row["analysis_json"]
        if not isinstance(analysis, dict):
            continue
        clarification = analysis.get("pending_clarification")
        if not isinstance(clarification, dict):
            continue
        clarification_id = clarification.get("clarificationId")
        if isinstance(clarification_id, str):
            connection.execute(
                requirements.update()
                .where(requirements.c.id == row["id"])
                .values(clarification_id=clarification_id)
            )

    with op.batch_alter_table("workflow_requirements") as batch_op:
        batch_op.create_unique_constraint(
            "uq_workflow_requirements_workflow_clarification",
            ["workflow_id", "clarification_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("workflow_requirements") as batch_op:
        batch_op.drop_constraint(
            "uq_workflow_requirements_workflow_clarification", type_="unique"
        )
        batch_op.drop_column("clarification_id")