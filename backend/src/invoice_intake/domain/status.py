"""Invoice lifecycle: the statuses and the only moves allowed between them.

    uploaded -> extracting -> needs_review -> approved -> exported
                              needs_review -> rejected

Approval and rejection are human decisions: AI output is a draft until a user acts on it.
"""

from enum import Enum

from .actors import ActorKind


class InvoiceStatus(str, Enum):
    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPORTED = "exported"


# For each status, the statuses it may move to and the actor kind allowed to make that move.
TRANSITIONS: dict[InvoiceStatus, dict[InvoiceStatus, ActorKind]] = {
    InvoiceStatus.UPLOADED: {InvoiceStatus.EXTRACTING: ActorKind.SYSTEM},
    InvoiceStatus.EXTRACTING: {InvoiceStatus.NEEDS_REVIEW: ActorKind.SYSTEM},
    InvoiceStatus.NEEDS_REVIEW: {
        InvoiceStatus.APPROVED: ActorKind.USER,
        InvoiceStatus.REJECTED: ActorKind.USER,
    },
    InvoiceStatus.APPROVED: {InvoiceStatus.EXPORTED: ActorKind.SYSTEM},
    InvoiceStatus.REJECTED: {},
    InvoiceStatus.EXPORTED: {},
}


def allowed_next(status: InvoiceStatus) -> frozenset[InvoiceStatus]:
    """The statuses an invoice in ``status`` may move to."""
    return frozenset(TRANSITIONS[status])


def is_terminal(status: InvoiceStatus) -> bool:
    return not TRANSITIONS[status]
