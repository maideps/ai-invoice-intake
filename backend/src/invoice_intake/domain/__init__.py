"""Domain layer: entities, rules and the invoice state machine.

Imports nothing from other layers and nothing outside the standard library
(enforced by arch-007, ``backend/tools/check_layer_imports.py``).
"""

from .actors import Actor, ActorKind
from .audit import AuditAction, AuditEvent
from .errors import (
    ActorNotPermittedError,
    ConcurrentModificationError,
    DomainError,
    InvalidInvoiceDataError,
    InvalidTransitionError,
)
from .invoice import Invoice, InvoiceFields, LineItem
from .repository import Document, InvoicePage, InvoiceRepository
from .status import TRANSITIONS, InvoiceStatus, allowed_next, is_terminal

__all__ = [
    "TRANSITIONS",
    "Actor",
    "ActorKind",
    "ActorNotPermittedError",
    "AuditAction",
    "AuditEvent",
    "ConcurrentModificationError",
    "Document",
    "DomainError",
    "InvalidInvoiceDataError",
    "InvalidTransitionError",
    "Invoice",
    "InvoiceFields",
    "InvoicePage",
    "InvoiceRepository",
    "InvoiceStatus",
    "LineItem",
    "allowed_next",
    "is_terminal",
]
