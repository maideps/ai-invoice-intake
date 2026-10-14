"""Initial schema: invoices, line items, append-only audit events, original documents.

Revision ID: 0001
Revises:
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = "'uploaded', 'extracting', 'needs_review', 'approved', 'rejected', 'exported'"


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("vendor_name", sa.Text(), nullable=True),
        sa.Column("invoice_number", sa.Text(), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("subtotal", sa.Numeric(), nullable=True),
        sa.Column("tax", sa.Numeric(), nullable=True),
        sa.Column("total", sa.Numeric(), nullable=True),
        sa.CheckConstraint(f"status IN ({STATUSES})", name="ck_invoices_status"),
        sa.PrimaryKeyConstraint("id", name="pk_invoices"),
    )
    op.create_index("ix_invoices_status_uploaded_at", "invoices", ["status", "uploaded_at"])
    op.create_index("ix_invoices_uploaded_at", "invoices", ["uploaded_at"])

    op.create_table(
        "invoice_line_items",
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(), nullable=False),
        sa.Column("unit_price", sa.Numeric(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name="fk_invoice_line_items_invoice_id_invoices",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("invoice_id", "position", name="pk_invoice_line_items"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_kind", sa.String(10), nullable=False),
        sa.Column("actor_name", sa.Text(), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.CheckConstraint("sequence >= 1", name="ck_audit_events_sequence"),
        sa.CheckConstraint(
            "actor_kind IN ('system', 'ai', 'user')", name="ck_audit_events_actor_kind"
        ),
        sa.CheckConstraint("action IN ('status_changed')", name="ck_audit_events_action"),
        sa.CheckConstraint(f"to_status IN ({STATUSES})", name="ck_audit_events_to_status"),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name="fk_audit_events_invoice_id_invoices",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
        sa.UniqueConstraint("invoice_id", "sequence", name="uq_audit_events_invoice_id_sequence"),
    )

    op.create_table(
        "invoice_documents",
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint("size > 0", name="ck_invoice_documents_size"),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name="fk_invoice_documents_invoice_id_invoices",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("invoice_id", name="pk_invoice_documents"),
    )

    # The audit trail is evidence: once written, a row can never change or disappear.
    op.execute(
        """
        CREATE FUNCTION audit_events_append_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only: % is not allowed', TG_OP
                USING ERRCODE = 'restrict_violation';
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_append_only()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION audit_events_append_only()")
    op.drop_table("invoice_documents")
    op.drop_table("audit_events")
    op.drop_table("invoice_line_items")
    op.drop_index("ix_invoices_uploaded_at", table_name="invoices")
    op.drop_index("ix_invoices_status_uploaded_at", table_name="invoices")
    op.drop_table("invoices")
