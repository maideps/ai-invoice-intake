"""The queue the services hand invoices to. The worker's Redis queue implements it (D-010)."""

import logging
from typing import Literal, Protocol
from uuid import UUID

log = logging.getLogger(__name__)

# What the worker should do with the invoice.
JobKind = Literal["extract", "export"]


class ExtractionQueue(Protocol):
    """Where invoices wait for the worker. Delivery may repeat, so consumers must be idempotent."""

    def enqueue(self, invoice_id: UUID, kind: JobKind = "extract") -> None: ...


class AfterCommitQueue:
    """Holds enqueues made during a transaction until it has committed.

    Enqueuing earlier would let the worker look for an invoice that is not stored yet (or never
    will be, if the transaction rolls back). If the real queue is unreachable at flush time the
    invoice is still stored in ``uploaded``; the worker's sweep queues it later.
    """

    def __init__(self) -> None:
        self.pending: list[tuple[UUID, JobKind]] = []

    def enqueue(self, invoice_id: UUID, kind: JobKind = "extract") -> None:
        self.pending.append((invoice_id, kind))

    def flush_to(self, queue: ExtractionQueue) -> None:
        for invoice_id, kind in self.pending:
            try:
                queue.enqueue(invoice_id, kind)
            except Exception:  # the change is committed; the worker's sweep will pick it up
                log.warning("could not queue invoice %s for %s", invoice_id, kind, exc_info=True)
        self.pending.clear()
