"""Use cases for AI extraction: one attempt at a time, each step in its own short transaction.

An attempt is ``begin`` (move to ``extracting``, fetch the document), the provider call (outside
any transaction, since a model can take many seconds), then ``complete`` (record the outcome) or
``fail`` (give up). ``ExtractionRunner`` drives an attempt; the worker decides about retries.
Jobs can arrive twice (queue redelivery), so every step tolerates an invoice that has moved on.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from invoice_intake.domain import (
    Actor,
    ActorKind,
    Document,
    ExtractionOutputError,
    ExtractionProvider,
    ExtractionProviderError,
    Invoice,
    InvoiceRepository,
    InvoiceStatus,
    RawExtraction,
    parse_extraction,
)

from .intake import InvoiceNotFoundError
from .queue import ExtractionQueue

SYSTEM = Actor(ActorKind.SYSTEM, "extraction-service")


class NotExtractableError(Exception):
    """The invoice is not (or no longer) waiting for extraction."""


@dataclass(frozen=True)
class ExtractionOutcome:
    invoice: Invoice
    accepted: bool
    errors: tuple[str, ...] = ()


class ExtractionService:
    """The steps of an attempt. One instance per transaction (see ``ExtractionServiceFactory``)."""

    def __init__(
        self,
        invoices: InvoiceRepository,
        queue: ExtractionQueue,
        *,
        clock: Callable[[], datetime],
    ) -> None:
        self._invoices = invoices
        self._queue = queue
        self._clock = clock

    def request(self, invoice_id: UUID, *, requested_by: Actor) -> Invoice:
        """Ask for extraction (again). A ``failed`` invoice goes back to ``extracting``, recorded
        as the requesting person's decision; ``uploaded`` and ``extracting`` are just queued."""
        invoice = self._get(invoice_id)
        if invoice.status is InvoiceStatus.FAILED:
            invoice.transition_to(InvoiceStatus.EXTRACTING, actor=requested_by, at=self._clock())
            self._invoices.save(invoice)
        elif invoice.status not in (InvoiceStatus.UPLOADED, InvoiceStatus.EXTRACTING):
            raise NotExtractableError(
                f"invoice {invoice_id} is {invoice.status.value}; extraction is already done"
            )
        self._queue.enqueue(invoice_id)
        return invoice

    def begin(self, invoice_id: UUID) -> Document:
        """Start an attempt: ``uploaded`` moves to ``extracting``; ``extracting`` resumes."""
        invoice = self._get(invoice_id)
        if invoice.status is InvoiceStatus.UPLOADED:
            invoice.transition_to(InvoiceStatus.EXTRACTING, actor=SYSTEM, at=self._clock())
            self._invoices.save(invoice)
        elif invoice.status is not InvoiceStatus.EXTRACTING:
            raise NotExtractableError(f"invoice {invoice_id} is {invoice.status.value}")
        document = self._invoices.get_document(invoice_id)
        if document is None:
            raise InvoiceNotFoundError(f"document of invoice {invoice_id} not found")
        return document

    def complete(self, invoice_id: UUID, raw: RawExtraction) -> ExtractionOutcome:
        """Record the provider's output: accepted output moves the invoice to ``needs_review``;
        rejected output is kept with its errors and the invoice stays in ``extracting``."""
        invoice = self._extracting(invoice_id)
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

    def fail(self, invoice_id: UUID, reason: str) -> Invoice:
        """Give up: ``extracting`` moves to ``failed`` with the reason in the audit trail."""
        invoice = self._extracting(invoice_id)
        invoice.transition_to(InvoiceStatus.FAILED, actor=SYSTEM, at=self._clock(), reason=reason)
        self._invoices.save(invoice)
        return invoice

    def requeue_stale_uploads(self, *, older_than: datetime) -> int:
        """Queue invoices still ``uploaded`` since before ``older_than`` (their job was lost,
        for example because Redis was down during the upload). Returns how many were queued."""
        queued, offset, page_size = 0, 0, 100
        while True:
            page = self._invoices.list_page(
                status=InvoiceStatus.UPLOADED, limit=page_size, offset=offset
            )
            for invoice in page.items:
                if invoice.uploaded_at < older_than:
                    self._queue.enqueue(invoice.id)
                    queued += 1
            offset += page_size
            if offset >= page.total:
                return queued

    def _get(self, invoice_id: UUID) -> Invoice:
        invoice = self._invoices.get(invoice_id)
        if invoice is None:
            raise InvoiceNotFoundError(f"invoice {invoice_id} not found")
        return invoice

    def _extracting(self, invoice_id: UUID) -> Invoice:
        invoice = self._get(invoice_id)
        if invoice.status is not InvoiceStatus.EXTRACTING:
            raise NotExtractableError(f"invoice {invoice_id} is {invoice.status.value}")
        return invoice


# Builds a service whose changes are committed when the context exits without an error.
ExtractionServiceFactory = Callable[[], AbstractContextManager[ExtractionService]]


class AttemptResult(str, Enum):
    ACCEPTED = "accepted"  # fields recorded, invoice in needs_review
    RETRY = "retry"  # provider error or rejected output, attempts left
    FAILED = "failed"  # out of attempts, invoice marked failed
    SKIPPED = "skipped"  # nothing to do: the invoice is gone or past extraction


@dataclass(frozen=True)
class AttemptOutcome:
    result: AttemptResult
    detail: str = ""


class ExtractionRunner:
    """Runs one extraction attempt. Retrying is the caller's job (the worker's queue)."""

    def __init__(
        self,
        services: ExtractionServiceFactory,
        provider: ExtractionProvider,
        *,
        max_attempts: int,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._services = services
        self._provider = provider
        self._max_attempts = max_attempts

    def run(self, invoice_id: UUID, attempt: int) -> AttemptOutcome:
        try:
            with self._services() as service:
                document = service.begin(invoice_id)
        except (InvoiceNotFoundError, NotExtractableError) as error:
            return AttemptOutcome(AttemptResult.SKIPPED, str(error))

        try:
            raw = self._provider.extract(document)  # no transaction open while the model works
        except ExtractionProviderError as error:
            return self._retry_or_fail(invoice_id, attempt, f"provider error: {error}")

        try:
            with self._services() as service:
                outcome = service.complete(invoice_id, raw)
        except NotExtractableError as error:  # finished elsewhere meanwhile (duplicate job)
            return AttemptOutcome(AttemptResult.SKIPPED, str(error))
        if outcome.accepted:
            return AttemptOutcome(AttemptResult.ACCEPTED)
        return self._retry_or_fail(
            invoice_id, attempt, f"output rejected: {'; '.join(outcome.errors)}"
        )

    def _retry_or_fail(self, invoice_id: UUID, attempt: int, problem: str) -> AttemptOutcome:
        if attempt < self._max_attempts:
            return AttemptOutcome(AttemptResult.RETRY, problem)
        reason = f"extraction failed after {attempt} attempt(s); last {problem}"
        try:
            with self._services() as service:
                service.fail(invoice_id, reason)
        except NotExtractableError as error:
            return AttemptOutcome(AttemptResult.SKIPPED, str(error))
        return AttemptOutcome(AttemptResult.FAILED, reason)
