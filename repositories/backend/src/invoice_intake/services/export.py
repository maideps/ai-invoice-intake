"""Use cases for exporting approved invoices to the accounting system's webhook (feat-010).

Like extraction (D-010), an attempt is short transactions around the slow part: ``begin``
(approved invoices only: build the payload), the HTTP delivery outside any transaction, then
``complete`` (move to ``exported``) or ``record_failure``. Delivery is at least once; receivers
de-duplicate on the ``Idempotency-Key``, which is the invoice id.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from invoice_intake.domain import (
    EXPORTER,
    Invoice,
    InvoiceRepository,
    InvoiceStatus,
)

from .extraction import AttemptOutcome, AttemptResult
from .intake import InvoiceNotFoundError
from .queue import ExtractionQueue

PAYLOAD_VERSION = 1


class ExportDeliveryError(Exception):
    """The webhook did not accept the delivery."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ExportSender(Protocol):
    def send(self, payload: dict[str, Any], *, idempotency_key: str) -> None:
        """Deliver once; raise ``ExportDeliveryError`` unless the receiver accepted it."""
        ...


class NotExportableError(Exception):
    """Only approved invoices are exported."""


def export_payload(invoice: Invoice) -> dict[str, Any]:
    """What the accounting system receives: the approved values and who approved them."""
    approval = next(
        event for event in reversed(invoice.events) if event.to_status is InvoiceStatus.APPROVED
    )
    return {
        "payload_version": PAYLOAD_VERSION,
        "invoice_id": str(invoice.id),
        "filename": invoice.filename,
        "approved_at": approval.occurred_at.isoformat(),
        "approved_by": approval.actor.name,
        "audit_version": invoice.version,
        "fields": invoice.fields.to_json(),
    }


class ExportService:
    """The steps of an export attempt. One instance per transaction."""

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

    def request(self, invoice_id: UUID) -> Invoice:
        """Queue (another) delivery attempt for an approved invoice."""
        invoice = self._approved(invoice_id)
        self._queue.enqueue(invoice_id, "export")
        return invoice

    def begin(self, invoice_id: UUID) -> dict[str, Any]:
        return export_payload(self._approved(invoice_id))

    def complete(self, invoice_id: UUID) -> Invoice:
        invoice = self._approved(invoice_id)
        invoice.transition_to(InvoiceStatus.EXPORTED, actor=EXPORTER, at=self._clock())
        self._invoices.save(invoice)
        return invoice

    def record_failure(
        self, invoice_id: UUID, *, attempt: int, error: ExportDeliveryError, final: bool
    ) -> Invoice:
        invoice = self._approved(invoice_id)
        invoice.record_export_failure(
            attempt=attempt,
            error=str(error),
            final=final,
            status_code=error.status_code,
            at=self._clock(),
        )
        self._invoices.save(invoice)
        return invoice

    def requeue_unsent(self, *, approved_before: datetime) -> int:
        """Queue approved invoices that never had a delivery attempt (their job was lost)."""
        queued, offset, page_size = 0, 0, 100
        while True:
            page = self._invoices.list_page(
                status=InvoiceStatus.APPROVED, limit=page_size, offset=offset
            )
            for invoice in page.items:
                status = invoice.export_status
                # While pending, the approval is the last event: nothing else happens in approved.
                waiting = status is not None and status.state == "pending"
                if waiting and invoice.events[-1].occurred_at < approved_before:
                    self._queue.enqueue(invoice.id, "export")
                    queued += 1
            offset += page_size
            if offset >= page.total:
                return queued

    def _approved(self, invoice_id: UUID) -> Invoice:
        invoice = self._invoices.get(invoice_id)
        if invoice is None:
            raise InvoiceNotFoundError(f"invoice {invoice_id} not found")
        if invoice.status is not InvoiceStatus.APPROVED:
            raise NotExportableError(
                f"invoice {invoice_id} is {invoice.status.value}; "
                "only approved invoices are exported"
            )
        return invoice


ExportServiceFactory = Callable[[], AbstractContextManager[ExportService]]


class ExportRunner:
    """Runs one delivery attempt. Retrying is the caller's job (the worker's queue)."""

    def __init__(
        self, services: ExportServiceFactory, sender: ExportSender, *, max_attempts: int
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._services = services
        self._sender = sender
        self._max_attempts = max_attempts

    def run(self, invoice_id: UUID, attempt: int) -> AttemptOutcome:
        try:
            with self._services() as service:
                payload = service.begin(invoice_id)
        except (InvoiceNotFoundError, NotExportableError) as error:
            return AttemptOutcome(AttemptResult.SKIPPED, str(error))

        try:
            self._sender.send(payload, idempotency_key=str(invoice_id))  # outside any transaction
        except ExportDeliveryError as error:
            final = attempt >= self._max_attempts
            try:
                with self._services() as service:
                    service.record_failure(invoice_id, attempt=attempt, error=error, final=final)
            except NotExportableError as gone:
                return AttemptOutcome(AttemptResult.SKIPPED, str(gone))
            result = AttemptResult.FAILED if final else AttemptResult.RETRY
            return AttemptOutcome(result, f"delivery failed: {error}")

        try:
            with self._services() as service:
                service.complete(invoice_id)
        except NotExportableError as error:  # exported by a duplicate job meanwhile
            return AttemptOutcome(AttemptResult.SKIPPED, str(error))
        return AttemptOutcome(AttemptResult.ACCEPTED, "delivered")
