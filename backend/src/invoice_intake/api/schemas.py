"""Response bodies. Money and quantities are decimal strings in JSON, never floats."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field, PlainSerializer

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
    to_status: InvoiceStatus | None
    reason: str | None
    details: dict[str, Any] | None

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
            details=dict(event.details) if event.details is not None else None,
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
    version: int  # send it back with edits and decisions (optimistic concurrency)
    uploaded_at: datetime
    fields: FieldsOut
    confidence: dict[str, float] | None  # per field, from the latest accepted extraction
    events: list[AuditEventOut]

    @classmethod
    def of(cls, invoice: Invoice) -> "InvoiceOut":
        fields = invoice.fields
        return cls(
            id=invoice.id,
            filename=invoice.filename,
            status=invoice.status,
            version=invoice.version,
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
            confidence=invoice.extraction_confidence,
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


class StatsOut(BaseModel):
    total: int
    by_status: dict[InvoiceStatus, int]  # every status, zero when there are none


# Request bodies for review. `version` is the invoice version the reviewer last saw.


class EditFieldsIn(BaseModel):
    version: int = Field(ge=1)
    fields: dict[str, Any] = Field(
        description="Fields to change, in the extraction JSON format; null clears a field."
    )


class ApproveIn(BaseModel):
    version: int = Field(ge=1)


class RejectIn(BaseModel):
    version: int = Field(ge=1)
    reason: str


class ProblemOut(BaseModel):
    """The `detail` of a 422 from the review endpoints: what failed, and every reason."""

    message: str
    errors: list[str]
