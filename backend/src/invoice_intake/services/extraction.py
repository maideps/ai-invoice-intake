"""Use case: run AI extraction for one invoice and record the outcome in its audit trail."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from invoice_intake.domain import (
    Actor,
    ActorKind,
    ExtractionOutputError,
    ExtractionProvider,
    Invoice,
    InvoiceRepository,
    InvoiceStatus,
    parse_extraction,
)

from .intake import InvoiceNotFoundError

SYSTEM = Actor(ActorKind.SYSTEM, "extraction-service")
EXTRACTABLE = (InvoiceStatus.UPLOADED, InvoiceStatus.EXTRACTING)


class NotExtractableError(Exception):
    """The invoice is past extraction (or never reached it)."""


@dataclass(frozen=True)
class ExtractionOutcome:
    invoice: Invoice
    accepted: bool
    errors: tuple[str, ...] = ()


class ExtractionService:
    def __init__(
        self,
        invoices: InvoiceRepository,
        provider: ExtractionProvider,
        *,
        clock: Callable[[], datetime],
    ) -> None:
        self._invoices = invoices
        self._provider = provider
        self._clock = clock

    def extract(self, invoice_id: UUID) -> ExtractionOutcome:
        """Extract fields for an ``uploaded`` (or still ``extracting``) invoice.

        Accepted output becomes the invoice's fields and the invoice moves to ``needs_review``.
        Rejected output is recorded with its errors and the invoice stays in ``extracting`` so a
        later attempt can continue. A provider failure (``ExtractionProviderError``) propagates
        and nothing is recorded.
        """
        invoice = self._invoices.get(invoice_id)
        if invoice is None:
            raise InvoiceNotFoundError(f"invoice {invoice_id} not found")
        if invoice.status not in EXTRACTABLE:
            raise NotExtractableError(
                f"invoice {invoice_id} is {invoice.status.value}; only uploaded or extracting "
                "invoices can be extracted"
            )
        document = self._invoices.get_document(invoice_id)
        if document is None:
            raise InvoiceNotFoundError(f"document of invoice {invoice_id} not found")

        if invoice.status is InvoiceStatus.UPLOADED:
            invoice.transition_to(InvoiceStatus.EXTRACTING, actor=SYSTEM, at=self._clock())
        raw = self._provider.extract(document)
        try:
            result = parse_extraction(raw)
        except ExtractionOutputError as error:
            invoice.record_rejected_extraction(
                provider=raw.provider,
                model=raw.model,
                output=raw.output,
                errors=error.errors,
                at=self._clock(),
            )
            self._invoices.save(invoice)
            return ExtractionOutcome(invoice, accepted=False, errors=tuple(error.errors))

        invoice.record_extraction(
            provider=result.provider,
            model=result.model,
            fields=result.fields,
            confidence=result.confidence,
            at=self._clock(),
        )
        invoice.transition_to(InvoiceStatus.NEEDS_REVIEW, actor=SYSTEM, at=self._clock())
        self._invoices.save(invoice)
        return ExtractionOutcome(invoice, accepted=True)


# Builds a service whose changes are committed when the context exits without an error.
ExtractionServiceFactory = Callable[[], AbstractContextManager[ExtractionService]]
