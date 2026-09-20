"""Create the initial IntegrationOps persistence schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "investigations",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("incident_id", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    for column in ("incident_id", "tenant_id", "classification", "confidence", "created_at"):
        op.create_index(f"ix_investigations_{column}", "investigations", [column])

    op.create_table(
        "investigation_feedback",
        sa.Column("feedback_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("corrected_root_cause", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["investigations.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("feedback_id"),
    )
    op.create_index("ix_investigation_feedback_run_id", "investigation_feedback", ["run_id"])

    op.create_table(
        "remediation_actions",
        sa.Column("action_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("transaction_reference", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("decided_by", sa.String(length=128), nullable=True),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=True),
        sa.Column("execution_result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["investigations.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("action_id"),
    )
    for column in ("run_id", "tenant_id", "status"):
        op.create_index(f"ix_remediation_actions_{column}", "remediation_actions", [column])

    op.create_table(
        "remediation_audit_events",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("action_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["action_id"], ["remediation_actions.action_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )
    for column in ("action_id", "tenant_id", "event_type", "created_at"):
        op.create_index(
            f"ix_remediation_audit_events_{column}",
            "remediation_audit_events",
            [column],
        )


def downgrade() -> None:
    op.drop_table("remediation_audit_events")
    op.drop_table("remediation_actions")
    op.drop_table("investigation_feedback")
    op.drop_table("investigations")
