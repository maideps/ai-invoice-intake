"""Reviewer edits: allow the fields_edited audit action.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIONS_0002 = "'status_changed', 'extraction_recorded', 'extraction_rejected'"


def upgrade() -> None:
    op.drop_constraint("ck_audit_events_action", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_events_action", "audit_events", f"action IN ({ACTIONS_0002}, 'fields_edited')"
    )


def downgrade() -> None:
    # The trail is append-only, so reviewer edits cannot be deleted to fit the old check.
    count = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM audit_events WHERE action = 'fields_edited'"))
        .scalar_one()
    )
    if count:
        raise RuntimeError(
            f"cannot downgrade below 0003: {count} fields_edited audit event(s) exist and the "
            "audit trail is append-only"
        )
    op.drop_constraint("ck_audit_events_action", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_events_action", "audit_events", f"action IN ({ACTIONS_0002})"
    )
