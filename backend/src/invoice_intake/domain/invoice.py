"""The invoice entity, its extracted fields and line items."""

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from .actors import Actor, ActorKind
from .audit import AuditAction, AuditEvent, require_aware
from .errors import (
    ActorNotPermittedError,
    DomainError,
    InvalidInvoiceDataError,
    InvalidTransitionError,
)
from .status import TRANSITIONS, InvoiceStatus

_CURRENCY = re.compile(r"^[A-Z]{3}$")
MAX_RECORDED_OUTPUT_CHARS = 20_000

# Audit actions that do not change status: the status they require and who may record them.
_NOTE_RULES: dict[AuditAction, tuple[InvoiceStatus, ActorKind]] = {
    AuditAction.EXTRACTION_RECORDED: (InvoiceStatus.EXTRACTING, ActorKind.AI),
    AuditAction.EXTRACTION_REJECTED: (InvoiceStatus.EXTRACTING, ActorKind.AI),
    AuditAction.FIELDS_EDITED: (InvoiceStatus.NEEDS_REVIEW, ActorKind.USER),
}

# Fields an invoice must have before a reviewer can approve it.
REQUIRED_FOR_APPROVAL = ("vendor_name", "invoice_number", "issue_date", "currency", "total")


class ApprovalBlockedError(InvalidInvoiceDataError):
    """Approval needs fields that are still empty. ``missing`` names them."""

    def __init__(self, missing: list[str]) -> None:
        super().__init__(f"cannot approve until these fields are filled: {', '.join(missing)}")
        self.missing = missing


def _require_amount(value: Decimal, field: str) -> None:
    # Money stays Decimal end to end; a float here would already carry rounding error.
    if not isinstance(value, Decimal) or not value.is_finite():
        raise InvalidInvoiceDataError(f"{field} must be a finite Decimal")
    if value < 0:
        raise InvalidInvoiceDataError(f"{field} must not be negative")


def _require_text(value: str | None, field: str) -> None:
    if value is not None and not value.strip():
        raise InvalidInvoiceDataError(f"{field} must not be blank")


@dataclass(frozen=True)
class LineItem:
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise InvalidInvoiceDataError("line item description must not be empty")
        for field in ("quantity", "unit_price", "amount"):
            _require_amount(getattr(self, field), field)
        if self.quantity == 0:
            raise InvalidInvoiceDataError("quantity must be greater than zero")


@dataclass(frozen=True)
class InvoiceFields:
    """Header fields and line items read from the document. Every field is empty until extraction.

    Totals are not cross-checked here: a mismatch is something to show the reviewer, not to reject.
    """

    vendor_name: str | None = None
    invoice_number: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    currency: str | None = None
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total: Decimal | None = None
    line_items: tuple[LineItem, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.vendor_name, "vendor_name")
        _require_text(self.invoice_number, "invoice_number")
        if self.currency is not None and not _CURRENCY.match(self.currency):
            raise InvalidInvoiceDataError("currency must be a three-letter ISO 4217 code")
        for field in ("subtotal", "tax", "total"):
            value = getattr(self, field)
            if value is not None:
                _require_amount(value, field)
        if self.issue_date and self.due_date and self.due_date < self.issue_date:
            raise InvalidInvoiceDataError("due_date must not be before issue_date")

    def to_json(self) -> dict[str, Any]:
        """JSON form: decimals as strings, dates as ISO strings (the extraction output format)."""

        def text(value: object) -> str | None:
            return None if value is None else str(value)

        return {
            "vendor_name": self.vendor_name,
            "invoice_number": self.invoice_number,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "currency": self.currency,
            "subtotal": text(self.subtotal),
            "tax": text(self.tax),
            "total": text(self.total),
            "line_items": [
                {
                    "description": item.description,
                    "quantity": str(item.quantity),
                    "unit_price": str(item.unit_price),
                    "amount": str(item.amount),
                }
                for item in self.line_items
            ],
        }


class Invoice:
    """An uploaded invoice. Its status changes only through ``transition_to``, which audits it."""

    def __init__(
        self,
        *,
        filename: str,
        uploaded_by: Actor,
        uploaded_at: datetime,
        id: UUID | None = None,
        fields: InvoiceFields | None = None,
    ) -> None:
        if not filename.strip():
            raise InvalidInvoiceDataError("filename must not be empty")
        require_aware(uploaded_at, "uploaded_at")
        self._id = id or uuid4()
        self._filename = filename
        self._uploaded_at = uploaded_at
        self._fields = fields or InvoiceFields()
        self._status = InvoiceStatus.UPLOADED
        self._events: list[AuditEvent] = [
            AuditEvent(
                invoice_id=self._id,
                sequence=1,
                occurred_at=uploaded_at,
                actor=uploaded_by,
                action=AuditAction.STATUS_CHANGED,
                from_status=None,
                to_status=InvoiceStatus.UPLOADED,
            )
        ]

    @classmethod
    def restore(
        cls,
        *,
        id: UUID,
        filename: str,
        uploaded_at: datetime,
        fields: InvoiceFields,
        events: Sequence[AuditEvent],
    ) -> "Invoice":
        """Rebuild a stored invoice by replaying its audit trail through the lifecycle rules.

        The status is whatever the trail ends in, so a stored status can never disagree with
        the history. A trail that the rules would not have produced is rejected.
        """
        if not events:
            raise InvalidInvoiceDataError("a stored invoice needs at least its upload event")
        invoice = cls(
            filename=filename,
            uploaded_by=events[0].actor,
            uploaded_at=uploaded_at,
            id=id,
            fields=fields,
        )
        if events[0] != invoice._events[0]:
            raise InvalidInvoiceDataError("the first audit event must be the upload")
        for event in events[1:]:
            try:
                if event.action is AuditAction.STATUS_CHANGED:
                    assert event.to_status is not None  # guaranteed by AuditEvent
                    replayed = invoice.transition_to(
                        event.to_status,
                        actor=event.actor,
                        at=event.occurred_at,
                        reason=event.reason,
                    )
                else:
                    # Field values come from storage (they may have been edited since); the
                    # replay only checks that the note was allowed when it was written.
                    replayed = invoice._note(
                        event.action,
                        actor=event.actor,
                        at=event.occurred_at,
                        details=event.details,
                    )
            except DomainError as error:
                raise InvalidInvoiceDataError(
                    f"stored audit event {event.sequence} breaks the lifecycle: {error}"
                ) from error
            if replayed != event:
                raise InvalidInvoiceDataError(
                    f"stored audit event {event.sequence} does not continue the trail"
                )
        return invoice

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def uploaded_at(self) -> datetime:
        return self._uploaded_at

    @property
    def status(self) -> InvoiceStatus:
        return self._status

    @property
    def fields(self) -> InvoiceFields:
        return self._fields

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        """The audit trail, oldest first."""
        return tuple(self._events)

    @property
    def version(self) -> int:
        """Grows with every audit event; clients send it back to prove they saw the latest state."""
        return len(self._events)

    @property
    def missing_for_approval(self) -> list[str]:
        return [name for name in REQUIRED_FOR_APPROVAL if getattr(self._fields, name) is None]

    @property
    def extraction_confidence(self) -> dict[str, float] | None:
        """Per-field confidence of the latest accepted extraction, if any."""
        for event in reversed(self._events):
            if event.action is AuditAction.EXTRACTION_RECORDED and event.details:
                return dict(event.details["confidence"])
        return None

    def record_extraction(
        self,
        *,
        provider: str,
        model: str,
        fields: InvoiceFields,
        confidence: Mapping[str, float],
        at: datetime,
    ) -> AuditEvent:
        """Take accepted AI output as the invoice's fields, keeping the output in the trail."""
        event = self._note(
            AuditAction.EXTRACTION_RECORDED,
            actor=_model_actor(provider, model),
            at=at,
            details={
                "provider": provider,
                "model": model,
                "fields": fields.to_json(),
                "confidence": dict(confidence),
            },
        )
        self._fields = fields
        return event

    def edit_fields(
        self, fields: InvoiceFields, *, actor: Actor, at: datetime
    ) -> AuditEvent | None:
        """A reviewer's correction: replace the fields and record each change (before and after).

        Returns ``None`` and records nothing when ``fields`` equals the current fields.
        """
        before, after = self._fields.to_json(), fields.to_json()
        changes = {
            name: {"from": before[name], "to": after[name]}
            for name in before
            if before[name] != after[name]
        }
        if not changes:
            return None
        event = self._note(
            AuditAction.FIELDS_EDITED, actor=actor, at=at, details={"changes": changes}
        )
        self._fields = fields
        return event

    def record_rejected_extraction(
        self, *, provider: str, model: str, output: object, errors: Sequence[str], at: datetime
    ) -> AuditEvent:
        """Keep AI output that failed validation, and why, without changing the fields."""
        return self._note(
            AuditAction.EXTRACTION_REJECTED,
            actor=_model_actor(provider, model),
            at=at,
            details={
                "provider": provider,
                "model": model,
                "errors": list(errors),
                "output": _bounded(output),
            },
        )

    def _note(
        self,
        action: AuditAction,
        *,
        actor: Actor,
        at: datetime,
        details: Mapping[str, Any] | None,
    ) -> AuditEvent:
        """Append an event that records something without changing status."""
        required_status, required_kind = _NOTE_RULES[action]
        if self._status is not required_status:
            raise InvalidTransitionError(
                f"cannot record {action.value} while the invoice is {self._status.value}"
            )
        if actor.kind is not required_kind:
            raise ActorNotPermittedError(
                f"only a {required_kind.value} actor may record {action.value}, "
                f"not a {actor.kind.value} actor"
            )
        require_aware(at, "at")
        if at < self._events[-1].occurred_at:
            raise InvalidInvoiceDataError("audit events must not go back in time")
        event = AuditEvent(
            invoice_id=self._id,
            sequence=len(self._events) + 1,
            occurred_at=at,
            actor=actor,
            action=action,
            from_status=None,
            to_status=None,
            details=details,
        )
        self._events.append(event)
        return event

    def transition_to(
        self,
        target: InvoiceStatus,
        *,
        actor: Actor,
        at: datetime,
        reason: str | None = None,
    ) -> AuditEvent:
        """Move to ``target`` and record it. On any rule violation, nothing changes."""
        allowed = TRANSITIONS[self._status]
        if target not in allowed:
            raise InvalidTransitionError(
                f"cannot move invoice from {self._status.value} to {target.value}"
            )
        required = allowed[target]
        if actor.kind is not required:
            raise ActorNotPermittedError(
                f"only a {required.value} actor may move an invoice to {target.value}, "
                f"not a {actor.kind.value} actor"
            )
        reason = (reason or "").strip() or None
        if target is InvoiceStatus.REJECTED and not reason:
            raise InvalidInvoiceDataError("a rejection needs a reason")
        if target is InvoiceStatus.APPROVED and self.missing_for_approval:
            raise ApprovalBlockedError(self.missing_for_approval)
        require_aware(at, "at")
        if at < self._events[-1].occurred_at:
            raise InvalidInvoiceDataError("audit events must not go back in time")

        event = AuditEvent(
            invoice_id=self._id,
            sequence=len(self._events) + 1,
            occurred_at=at,
            actor=actor,
            action=AuditAction.STATUS_CHANGED,
            from_status=self._status,
            to_status=target,
            reason=reason,
        )
        self._events.append(event)
        self._status = target
        return event

    def __repr__(self) -> str:
        return f"Invoice(id={self._id}, filename={self._filename!r}, status={self._status.value})"


def _model_actor(provider: str, model: str) -> Actor:
    return Actor(ActorKind.AI, f"{provider}:{model}")


def _bounded(output: object) -> object:
    """The output itself when it is small JSON; otherwise a truncated text form of it."""
    try:
        text = json.dumps(output, allow_nan=False)
    except (TypeError, ValueError):
        text = None
    if text is not None and len(text) <= MAX_RECORDED_OUTPUT_CHARS:
        return output
    raw = output if isinstance(output, str) else (text or repr(output))
    return {"truncated": raw[:MAX_RECORDED_OUTPUT_CHARS], "original_length": len(raw)}
