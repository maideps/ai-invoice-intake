"""Failed status: extraction can give up after its retries.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES_0003 = "'uploaded', 'extracting', 'needs_review', 'approved', 'rejected', 'exported'"
CHECKS = (("invoices", "status"), ("audit_events", "to_status"))


def _replace_checks(statuses: str) -> None:
    for table, column in CHECKS:
        name = f"ck_{table}_{column}"
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, f"{column} IN ({statuses})")


def upgrade() -> None:
    _replace_checks(f"{STATUSES_0003}, 'failed'")


def downgrade() -> None:
    # Failed invoices and their audit events cannot be removed (the trail is append-only).
    count = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT (SELECT count(*) FROM invoices WHERE status = 'failed') + "
                "(SELECT count(*) FROM audit_events "
                "WHERE 'failed' IN (from_status, to_status))"
            )
        )
        .scalar_one()
    )
    if count:
        raise RuntimeError(
            f"cannot downgrade below 0004: {count} failed invoice row(s) or audit event(s) exist "
            "and the audit trail is append-only"
        )
    _replace_checks(STATUSES_0003)
