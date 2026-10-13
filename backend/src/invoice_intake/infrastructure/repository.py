"""``InvoiceRepository`` on PostgreSQL. Maps rows to domain objects and back."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from invoice_intake.domain import (
    Actor,
    ActorKind,
    AuditAction,
    AuditEvent,
    ConcurrentModificationError,
    Document,
    Invoice,
    InvoiceFields,
    InvoicePage,
    InvoiceStatus,
    LineItem,
)

from .tables import AuditEventRow, DocumentRow, InvoiceRow, LineItemRow

# Reads load an invoice with its line items and events in ONE statement. Under PostgreSQL's
# default isolation (read committed) every statement sees its own snapshot, so separate queries
# could pair the invoice row from before a concurrent save with events from after it.
_IN_ONE_SNAPSHOT = (joinedload(InvoiceRow.line_items), joinedload(InvoiceRow.events))
# save() locks the invoice row first, so nothing changes under it and separate queries are fine
# (FOR UPDATE cannot be combined with the outer joins of joinedload).
_WITH_CHILDREN = (selectinload(InvoiceRow.line_items), selectinload(InvoiceRow.events))


class SqlInvoiceRepository:
    """Works inside the caller's session and transaction; it flushes but never commits."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, invoice: Invoice, document: Document) -> None:
        row = InvoiceRow(
            id=invoice.id,
            filename=invoice.filename,
            uploaded_at=invoice.uploaded_at,
            status=invoice.status.value,
        )
        _write_fields(row, invoice.fields)
        row.line_items = _line_item_rows(invoice)
        self._session.add(row)
        # Write the invoice row first: the document and event rows reference it by foreign key,
        # and only line items are linked through an ORM relationship that orders the inserts.
        self._session.flush()
        self._session.add_all(_event_row(event) for event in invoice.events)
        self._session.add(
            DocumentRow(
                invoice_id=invoice.id,
                content_type=document.content_type,
                size=document.size,
                sha256=document.sha256,
                content=document.content,
            )
        )
        self._session.flush()

    def get(self, invoice_id: UUID) -> Invoice | None:
        query = select(InvoiceRow).where(InvoiceRow.id == invoice_id).options(*_IN_ONE_SNAPSHOT)
        row = (
            self._session.scalars(query.execution_options(populate_existing=True)).unique().first()
        )
        return None if row is None else _to_domain(row)

    def list_page(self, *, status: InvoiceStatus | None, limit: int, offset: int) -> InvoicePage:
        query = select(InvoiceRow)
        if status is not None:
            query = query.where(InvoiceRow.status == status.value)
        total = self._session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self._session.scalars(
            query.options(*_IN_ONE_SNAPSHOT)
            .order_by(InvoiceRow.uploaded_at.desc(), InvoiceRow.id.desc())
            .limit(limit)
            .offset(offset)
            .execution_options(populate_existing=True)
        ).unique()
        return InvoicePage(items=tuple(_to_domain(row) for row in rows), total=total)

    def save(self, invoice: Invoice) -> None:
        # Lock the invoice row so concurrent saves of the same invoice run one after another,
        # then check that the stored trail is a prefix of ours (optimistic concurrency).
        row = self._session.get(
            InvoiceRow,
            invoice.id,
            options=_WITH_CHILDREN,
            with_for_update=True,
            populate_existing=True,
        )
        if row is None:
            raise LookupError(f"invoice {invoice.id} is not stored; use add()")
        stored = [_event_from_row(event) for event in row.events]
        if list(invoice.events[: len(stored)]) != stored:
            raise ConcurrentModificationError(
                f"invoice {invoice.id} changed since it was loaded; reload and retry"
            )

        row.status = invoice.status.value
        _write_fields(row, invoice.fields)
        if [_line_item_from_row(item) for item in row.line_items] != list(
            invoice.fields.line_items
        ):
            row.line_items.clear()
            self._session.flush()
            row.line_items.extend(_line_item_rows(invoice))
        self._session.add_all(_event_row(event) for event in invoice.events[len(stored) :])
        try:
            self._session.flush()
        except IntegrityError as error:  # a concurrent writer took the same sequence number
            raise ConcurrentModificationError(
                f"invoice {invoice.id} changed while saving; reload and retry"
            ) from error

    def get_document(self, invoice_id: UUID) -> Document | None:
        row = self._session.get(DocumentRow, invoice_id)
        return None if row is None else Document(content_type=row.content_type, content=row.content)


def _write_fields(row: InvoiceRow, fields: InvoiceFields) -> None:
    row.vendor_name = fields.vendor_name
    row.invoice_number = fields.invoice_number
    row.issue_date = fields.issue_date
    row.due_date = fields.due_date
    row.currency = fields.currency
    row.subtotal = fields.subtotal
    row.tax = fields.tax
    row.total = fields.total


def _line_item_rows(invoice: Invoice) -> list[LineItemRow]:
    return [
        LineItemRow(
            invoice_id=invoice.id,
            position=position,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            amount=item.amount,
        )
        for position, item in enumerate(invoice.fields.line_items, start=1)
    ]


def _line_item_from_row(row: LineItemRow) -> LineItem:
    return LineItem(
        description=row.description,
        quantity=row.quantity,
        unit_price=row.unit_price,
        amount=row.amount,
    )


def _event_row(event: AuditEvent) -> AuditEventRow:
    return AuditEventRow(
        invoice_id=event.invoice_id,
        sequence=event.sequence,
        occurred_at=event.occurred_at,
        actor_kind=event.actor.kind.value,
        actor_name=event.actor.name,
        action=event.action.value,
        from_status=event.from_status.value if event.from_status else None,
        to_status=event.to_status.value if event.to_status else None,
        reason=event.reason,
        details=dict(event.details) if event.details is not None else None,
    )


def _event_from_row(row: AuditEventRow) -> AuditEvent:
    return AuditEvent(
        invoice_id=row.invoice_id,
        sequence=row.sequence,
        occurred_at=row.occurred_at,
        actor=Actor(ActorKind(row.actor_kind), row.actor_name),
        action=AuditAction(row.action),
        from_status=InvoiceStatus(row.from_status) if row.from_status else None,
        to_status=InvoiceStatus(row.to_status) if row.to_status else None,
        reason=row.reason,
        details=row.details,
    )


def _to_domain(row: InvoiceRow) -> Invoice:
    invoice = Invoice.restore(
        id=row.id,
        filename=row.filename,
        uploaded_at=row.uploaded_at,
        fields=InvoiceFields(
            vendor_name=row.vendor_name,
            invoice_number=row.invoice_number,
            issue_date=row.issue_date,
            due_date=row.due_date,
            currency=row.currency,
            subtotal=row.subtotal,
            tax=row.tax,
            total=row.total,
            line_items=tuple(_line_item_from_row(item) for item in row.line_items),
        ),
        events=[_event_from_row(event) for event in row.events],
    )
    if invoice.status.value != row.status:
        raise ValueError(
            f"stored status {row.status!r} of invoice {row.id} disagrees with its audit trail"
        )
    return invoice
