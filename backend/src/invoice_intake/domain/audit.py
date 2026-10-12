"""Audit trail: who did what to an invoice, and when. Events are never changed or removed."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from .actors import Actor
from .errors import InvalidInvoiceDataError
from .status import InvoiceStatus


class AuditAction(str, Enum):
    STATUS_CHANGED = "status_changed"
    EXTRACTION_RECORDED = "extraction_recorded"  # AI output accepted; details hold it
    EXTRACTION_REJECTED = "extraction_rejected"  # AI output failed validation; details hold why


@dataclass(frozen=True)
class AuditEvent:
    """One entry in an invoice's trail.

    ``from_status`` and ``to_status`` are set only on ``status_changed`` events. ``details`` is a
    JSON object (for example the model output) and is stored as a detached, JSON-safe copy.
    """

    invoice_id: UUID
    sequence: int
    occurred_at: datetime
    actor: Actor
    action: AuditAction
    from_status: InvoiceStatus | None
    to_status: InvoiceStatus | None
    reason: str | None = None
    details: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise InvalidInvoiceDataError("audit sequence starts at 1")
        require_aware(self.occurred_at, "occurred_at")
        changes_status = self.action is AuditAction.STATUS_CHANGED
        if changes_status and self.to_status is None:
            raise InvalidInvoiceDataError("a status_changed event needs to_status")
        if not changes_status and (self.from_status or self.to_status):
            raise InvalidInvoiceDataError(f"a {self.action.value} event has no status change")
        if self.details is not None:
            object.__setattr__(self, "details", _json_copy(self.details))


def require_aware(value: datetime, field: str) -> None:
    """Reject naive datetimes, so stored times are never ambiguous."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidInvoiceDataError(f"{field} must be timezone-aware")


def _json_copy(details: Mapping[str, Any]) -> dict[str, Any]:
    """A detached deep copy in the exact form the database gives back (tuples become lists).

    Storing the round-tripped copy means an event compares equal before and after storage.
    """
    if not isinstance(details, Mapping):
        raise InvalidInvoiceDataError("audit details must be a JSON object")
    try:
        copied: dict[str, Any] = json.loads(json.dumps(dict(details), allow_nan=False))
    except (TypeError, ValueError) as error:  # not serialisable, or NaN / infinity
        raise InvalidInvoiceDataError(f"audit details must be JSON-safe: {error}") from error
    return copied
