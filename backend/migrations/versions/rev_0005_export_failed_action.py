"""Export deliveries: allow the export_failed audit action.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIONS_0004 = "'status_changed', 'extraction_recorded', 'extraction_rejected', 'fields_edited'"


def upgrade() -> None:
    op.drop_constraint("ck_audit_events_action", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_events_action", "audit_events", f"action IN ({ACTIONS_0004}, 'export_failed')"
    )


def downgrade() -> None:
    # The trail is append-only, so failed deliveries cannot be deleted to fit the old check.
    count = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM audit_events WHERE action = 'export_failed'"))
        .scalar_one()
    )
    if count:
        raise RuntimeError(
            f"cannot downgrade below 0005: {count} export_failed audit event(s) exist and the "
            "audit trail is append-only"
        )
    op.drop_constraint("ck_audit_events_action", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_events_action", "audit_events", f"action IN ({ACTIONS_0004})"
    )
