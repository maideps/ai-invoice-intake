"""Errors raised when a domain rule is broken."""


class DomainError(Exception):
    """Base class for every domain rule violation."""


class InvalidTransitionError(DomainError):
    """The invoice lifecycle does not allow moving between these two statuses."""


class ActorNotPermittedError(DomainError):
    """The status change is allowed, but not for this kind of actor."""


class InvalidInvoiceDataError(DomainError, ValueError):
    """An invoice, line item or audit value is malformed."""
