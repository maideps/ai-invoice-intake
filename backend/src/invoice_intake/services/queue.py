"""The queue the services hand invoices to. The worker's Redis queue implements it (D-010)."""

import logging
from typing import Protocol
from uuid import UUID

log = logging.getLogger(__name__)


class ExtractionQueue(Protocol):
    """Where invoices wait for the worker. Delivery may repeat, so consumers must be idempotent."""

    def enqueue(self, invoice_id: UUID) -> None: ...


class AfterCommitQueue:
    """Holds enqueues made during a transaction until it has committed.

    Enqueuing earlier would let the worker look for an invoice that is not stored yet (or never
    will be, if the transaction rolls back). If the real queue is unreachable at flush time the
    invoice is still stored in ``uploaded``; the worker's sweep queues it later.
    """

    def __init__(self) -> None:
        self.pending: list[UUID] = []

    def enqueue(self, invoice_id: UUID) -> None:
        self.pending.append(invoice_id)

    def flush_to(self, queue: ExtractionQueue) -> None:
        for invoice_id in self.pending:
            try:
                queue.enqueue(invoice_id)
            except Exception:  # the upload is committed; the sweep will pick it up
                log.warning("could not queue invoice %s for extraction", invoice_id, exc_info=True)
        self.pending.clear()
