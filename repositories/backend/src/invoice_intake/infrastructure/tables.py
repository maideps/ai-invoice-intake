"""PostgreSQL schema as SQLAlchemy models. Alembic migrations create it; keep the two in step.

Money and quantities use unconstrained ``numeric`` so values come back with the exact scale
they were stored with. Enum-like columns are text with CHECK constraints.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from invoice_intake.domain import ActorKind, AuditAction, InvoiceStatus

# The migrations spell these out literally; a test checks the database accepts every value.
STATUSES = tuple(status.value for status in InvoiceStatus)
ACTOR_KINDS = tuple(kind.value for kind in ActorKind)
ACTIONS = tuple(action.value for action in AuditAction)


def _one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_N_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class InvoiceRow(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint(_one_of("status", STATUSES), name="status"),
        Index(None, "status", "uploaded_at"),
        Index(None, "uploaded_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20))
    vendor_name: Mapped[str | None] = mapped_column(Text)
    invoice_number: Mapped[str | None] = mapped_column(Text)
    issue_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str | None] = mapped_column(String(3))
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric)
    tax: Mapped[Decimal | None] = mapped_column(Numeric)
    total: Mapped[Decimal | None] = mapped_column(Numeric)

    line_items: Mapped[list["LineItemRow"]] = relationship(
        order_by="LineItemRow.position", cascade="all, delete-orphan"
    )
    events: Mapped[list["AuditEventRow"]] = relationship(order_by="AuditEventRow.sequence")


class LineItemRow(Base):
    __tablename__ = "invoice_line_items"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric)
    unit_price: Mapped[Decimal] = mapped_column(Numeric)
    amount: Mapped[Decimal] = mapped_column(Numeric)


class AuditEventRow(Base):
    """Append-only: a database trigger rejects UPDATE and DELETE (see the initial migration)."""

    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("invoice_id", "sequence"),
        CheckConstraint("sequence >= 1", name="sequence"),
        CheckConstraint(_one_of("actor_kind", ACTOR_KINDS), name="actor_kind"),
        CheckConstraint(_one_of("action", ACTIONS), name="action"),
        CheckConstraint(_one_of("to_status", STATUSES), name="to_status"),
        # Status columns are filled exactly for status changes (see migration 0002).
        CheckConstraint(
            "(action = 'status_changed') = (to_status IS NOT NULL) "
            "AND (action = 'status_changed' OR from_status IS NULL)",
            name="status_change",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="RESTRICT"))
    sequence: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_kind: Mapped[str] = mapped_column(String(10))
    actor_name: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class DocumentRow(Base):
    __tablename__ = "invoice_documents"
    __table_args__ = (CheckConstraint("size > 0", name="size"),)

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), primary_key=True
    )
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    content: Mapped[bytes] = mapped_column(LargeBinary)
