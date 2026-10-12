"""Extraction audit events: JSON details, status columns only for status changes.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_ACTIONS = "'extraction_recorded', 'extraction_rejected'"


def upgrade() -> None:
    op.add_column("audit_events", sa.Column("details", postgresql.JSONB(), nullable=True))
    op.alter_column("audit_events", "to_status", existing_type=sa.String(20), nullable=True)
    op.drop_constraint("ck_audit_events_action", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_events_action",
        "audit_events",
        f"action IN ('status_changed', {NEW_ACTIONS})",
    )
    op.create_check_constraint(
        "ck_audit_events_status_change",
        "audit_events",
        "(action = 'status_changed') = (to_status IS NOT NULL) "
        "AND (action = 'status_changed' OR from_status IS NULL)",
    )


def downgrade() -> None:
    # The trail is append-only (trigger), so extraction events cannot be deleted to make the
    # old schema fit. Refuse rather than lose evidence.
    count = (
        op.get_bind()
        .execute(sa.text(f"SELECT count(*) FROM audit_events WHERE action IN ({NEW_ACTIONS})"))
        .scalar_one()
    )
    if count:
        raise RuntimeError(
            f"cannot downgrade below 0002: {count} extraction audit event(s) exist and the "
            "audit trail is append-only"
        )
    op.drop_constraint("ck_audit_events_status_change", "audit_events", type_="check")
    op.drop_constraint("ck_audit_events_action", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_events_action", "audit_events", "action IN ('status_changed')"
    )
    op.alter_column("audit_events", "to_status", existing_type=sa.String(20), nullable=False)
    op.drop_column("audit_events", "details")
