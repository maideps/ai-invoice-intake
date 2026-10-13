"""Use cases for human review: correct fields, approve, reject.

Every call carries the ``version`` the reviewer last saw. If the invoice has changed since (a
colleague edited it, extraction ran again), the call is refused, so nobody approves or overwrites
values they have not seen.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from uuid import UUID

from invoice_intake.domain import (
    Actor,
    Invoice,
    InvoiceRepository,
    InvoiceStatus,
    parse_field_patch,
)

from .intake import InvoiceNotFoundError


class VersionConflictError(Exception):
    """The invoice changed after the reviewer loaded it."""

    def __init__(self, invoice_id: UUID, expected: int, current: int) -> None:
        super().__init__(
            f"invoice {invoice_id} is at version {current}, not {expected}; reload it and retry"
        )
        self.current = current


class ReviewService:
    def __init__(self, invoices: InvoiceRepository, *, clock: Callable[[], datetime]) -> None:
        self._invoices = invoices
        self._clock = clock

    def edit_fields(
        self, invoice_id: UUID, *, version: int, patch: object, reviewer: Actor
    ) -> Invoice:
        """Apply a partial edit (JSON field values). An edit that changes nothing records nothing.

        Raises ``FieldValuesError`` for invalid values and ``InvalidTransitionError`` outside
        ``needs_review``.
        """
        invoice = self._load(invoice_id, version)
        fields = parse_field_patch(invoice.fields, patch)
        if invoice.edit_fields(fields, actor=reviewer, at=self._clock()) is not None:
            self._invoices.save(invoice)
        return invoice

    def approve(self, invoice_id: UUID, *, version: int, reviewer: Actor) -> Invoice:
        """Raises ``ApprovalBlockedError`` while required fields are empty."""
        return self._decide(invoice_id, version, InvoiceStatus.APPROVED, reviewer, reason=None)

    def reject(self, invoice_id: UUID, *, version: int, reviewer: Actor, reason: str) -> Invoice:
        """Raises ``InvalidInvoiceDataError`` when the reason is blank."""
        return self._decide(invoice_id, version, InvoiceStatus.REJECTED, reviewer, reason=reason)

    def _decide(
        self,
        invoice_id: UUID,
        version: int,
        target: InvoiceStatus,
        reviewer: Actor,
        reason: str | None,
    ) -> Invoice:
        invoice = self._load(invoice_id, version)
        invoice.transition_to(target, actor=reviewer, at=self._clock(), reason=reason)
        self._invoices.save(invoice)
        return invoice

    def _load(self, invoice_id: UUID, version: int) -> Invoice:
        invoice = self._invoices.get(invoice_id)
        if invoice is None:
            raise InvoiceNotFoundError(f"invoice {invoice_id} not found")
        if invoice.version != version:
            raise VersionConflictError(invoice_id, version, invoice.version)
        return invoice


# Builds a service whose changes are committed when the context exits without an error.
ReviewServiceFactory = Callable[[], AbstractContextManager[ReviewService]]
