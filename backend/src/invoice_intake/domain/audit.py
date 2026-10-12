"""Audit trail: who did what to an invoice, and when. Events are never changed or removed."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from .actors import Actor
from .errors import InvalidInvoiceDataError
from .status import InvoiceStatus


class AuditAction(str, Enum):
    """What happened. Later features add actions for AI output and field edits."""

    STATUS_CHANGED = "status_changed"


@dataclass(frozen=True)
class AuditEvent:
    invoice_id: UUID
    sequence: int
    occurred_at: datetime
    actor: Actor
    action: AuditAction
    from_status: InvoiceStatus | None
    to_status: InvoiceStatus
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise InvalidInvoiceDataError("audit sequence starts at 1")
        require_aware(self.occurred_at, "occurred_at")


def require_aware(value: datetime, field: str) -> None:
    """Reject naive datetimes, so stored times are never ambiguous."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidInvoiceDataError(f"{field} must be timezone-aware")
