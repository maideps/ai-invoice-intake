"""Sign-in: accounts and their sessions (D-019).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_accounts"),
        sa.UniqueConstraint("username", name="uq_accounts_username"),
        sa.CheckConstraint("role IN ('viewer', 'reviewer', 'admin')", name="ck_accounts_role"),
        sa.CheckConstraint("username = lower(username)", name="ck_accounts_username_lower"),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("token_hash", name="pk_sessions"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_sessions_account_id_accounts",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_sessions_account_id", "sessions", ["account_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])


def downgrade() -> None:
    # Audit events keep the usernames as text, so the trail stays readable without accounts.
    op.drop_table("sessions")
    op.drop_table("accounts")
