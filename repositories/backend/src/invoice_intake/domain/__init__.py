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
from .extraction import (
    OUTPUT_SCHEMA,
    ExtractionOutputError,
    ExtractionProvider,
    ExtractionProviderError,
    ExtractionResult,
    RawExtraction,
    empty_output,
    parse_extraction,
)
from .field_values import FIELD_NAMES, FieldValuesError, parse_field_patch
from .invoice import (
    EXPORTER,
    REQUIRED_FOR_APPROVAL,
    ApprovalBlockedError,
    ExportStatus,
    Invoice,
    InvoiceFields,
    LineItem,
)
from .repository import Document, InvoicePage, InvoiceRepository
from .status import TRANSITIONS, InvoiceStatus, allowed_next, is_terminal

__all__ = [
    "EXPORTER",
    "FIELD_NAMES",
    "OUTPUT_SCHEMA",
    "REQUIRED_FOR_APPROVAL",
    "TRANSITIONS",
    "Actor",
    "ActorKind",
    "ActorNotPermittedError",
    "ApprovalBlockedError",
    "AuditAction",
    "AuditEvent",
    "ConcurrentModificationError",
    "Document",
    "DomainError",
    "ExtractionOutputError",
    "ExtractionProvider",
    "ExtractionProviderError",
    "ExportStatus",
    "ExtractionResult",
    "FieldValuesError",
    "InvalidInvoiceDataError",
    "InvalidTransitionError",
    "Invoice",
    "InvoiceFields",
    "InvoicePage",
    "InvoiceRepository",
    "InvoiceStatus",
    "LineItem",
    "RawExtraction",
    "allowed_next",
    "empty_output",
    "is_terminal",
    "parse_field_patch",
    "parse_extraction",
]
