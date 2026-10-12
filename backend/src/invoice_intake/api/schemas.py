"""Response bodies. Money and quantities are decimal strings in JSON, never floats."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, PlainSerializer

from invoice_intake.domain import AuditEvent, Invoice, InvoicePage, InvoiceStatus

DecimalString = Annotated[Decimal, PlainSerializer(str, return_type=str, when_used="json")]


class LineItemOut(BaseModel):
    description: str
    quantity: DecimalString
    unit_price: DecimalString
    amount: DecimalString


class FieldsOut(BaseModel):
    vendor_name: str | None
    invoice_number: str | None
    issue_date: date | None
    due_date: date | None
    currency: str | None
    subtotal: DecimalString | None
    tax: DecimalString | None
    total: DecimalString | None
    line_items: list[LineItemOut]


class AuditEventOut(BaseModel):
    sequence: int
    occurred_at: datetime
    actor_kind: str
    actor_name: str
    action: str
    from_status: InvoiceStatus | None
    to_status: InvoiceStatus
    reason: str | None

    @classmethod
    def of(cls, event: AuditEvent) -> "AuditEventOut":
        return cls(
            sequence=event.sequence,
            occurred_at=event.occurred_at,
            actor_kind=event.actor.kind.value,
            actor_name=event.actor.name,
            action=event.action.value,
            from_status=event.from_status,
            to_status=event.to_status,
            reason=event.reason,
        )


class InvoiceSummaryOut(BaseModel):
    id: UUID
    filename: str
    status: InvoiceStatus
    uploaded_at: datetime
    vendor_name: str | None
    currency: str | None
    total: DecimalString | None

    @classmethod
    def of(cls, invoice: Invoice) -> "InvoiceSummaryOut":
        return cls(
            id=invoice.id,
            filename=invoice.filename,
            status=invoice.status,
            uploaded_at=invoice.uploaded_at,
            vendor_name=invoice.fields.vendor_name,
            currency=invoice.fields.currency,
            total=invoice.fields.total,
        )


class InvoiceOut(BaseModel):
    id: UUID
    filename: str
    status: InvoiceStatus
    uploaded_at: datetime
    fields: FieldsOut
    events: list[AuditEventOut]

    @classmethod
    def of(cls, invoice: Invoice) -> "InvoiceOut":
        fields = invoice.fields
        return cls(
            id=invoice.id,
            filename=invoice.filename,
            status=invoice.status,
            uploaded_at=invoice.uploaded_at,
            fields=FieldsOut(
                vendor_name=fields.vendor_name,
                invoice_number=fields.invoice_number,
                issue_date=fields.issue_date,
                due_date=fields.due_date,
                currency=fields.currency,
                subtotal=fields.subtotal,
                tax=fields.tax,
                total=fields.total,
                line_items=[
                    LineItemOut(
                        description=item.description,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        amount=item.amount,
                    )
                    for item in fields.line_items
                ],
            ),
            events=[AuditEventOut.of(event) for event in invoice.events],
        )


class InvoicePageOut(BaseModel):
    items: list[InvoiceSummaryOut]
    total: int
    limit: int
    offset: int

    @classmethod
    def of(cls, page: InvoicePage, *, limit: int, offset: int) -> "InvoicePageOut":
        return cls(
            items=[InvoiceSummaryOut.of(invoice) for invoice in page.items],
            total=page.total,
            limit=limit,
            offset=offset,
        )
