"""Sign-in rate limiting: failed sign-ins (D-022).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sign_in_failures",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("client", sa.String(64), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sign_in_failures"),
    )
    op.create_index(
        "ix_sign_in_failures_username_failed_at", "sign_in_failures", ["username", "failed_at"]
    )
    op.create_index(
        "ix_sign_in_failures_client_failed_at", "sign_in_failures", ["client", "failed_at"]
    )


def downgrade() -> None:
    op.drop_table("sign_in_failures")
