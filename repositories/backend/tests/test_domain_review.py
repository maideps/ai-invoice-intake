from datetime import date
from decimal import Decimal

import pytest

from invoice_intake.domain import (
    REQUIRED_FOR_APPROVAL,
    ActorKind,
    ActorNotPermittedError,
    ApprovalBlockedError,
    AuditAction,
    FieldValuesError,
    InvalidTransitionError,
    Invoice,
    InvoiceFields,
    InvoiceStatus,
    LineItem,
    parse_field_patch,
)

from .domain_helpers import ACTORS, READY_FIELDS, at, invoice_in, new_invoice

S = InvoiceStatus
USER = ACTORS[ActorKind.USER]


# Field patches -------------------------------------------------------------------------------


def test_patch_changes_only_the_named_fields() -> None:
    patched = parse_field_patch(READY_FIELDS, {"total": "120.50", "due_date": "2026-10-31"})

    assert patched.total == Decimal("120.50")
    assert patched.due_date == date(2026, 10, 31)
    assert patched.vendor_name == READY_FIELDS.vendor_name


def test_null_clears_a_field_and_line_items_are_replaced_whole() -> None:
    lines = [{"description": "Toner", "quantity": "2", "unit_price": "40.00", "amount": "80.00"}]

    patched = parse_field_patch(READY_FIELDS, {"invoice_number": None, "line_items": lines})

    assert patched.invoice_number is None
    assert patched.line_items == (
        LineItem("Toner", Decimal("2"), Decimal("40.00"), Decimal("80.00")),
    )
    assert parse_field_patch(patched, {"line_items": []}).line_items == ()


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({}, "non-empty JSON object"),
        (["total", "1"], "non-empty JSON object"),
        ({"iban": "DE00"}, "unknown keys iban"),
        ({"total": "1.234,50"}, "fields.total must be a decimal string"),
        ({"total": 12.5}, "fields.total must be a decimal string"),
        ({"issue_date": "01/10/2026"}, "fields.issue_date must be an ISO date"),
        ({"currency": "eur"}, "currency must be a three-letter ISO 4217 code"),
        ({"due_date": "2026-09-01"}, "due_date must not be before issue_date"),  # vs. current
        ({"line_items": None}, "fields.line_items must be a list"),
    ],
)
def test_invalid_patches_are_refused(patch: object, message: str) -> None:
    with pytest.raises(FieldValuesError, match=message):
        parse_field_patch(READY_FIELDS, patch)


def test_every_problem_in_a_patch_is_reported() -> None:
    with pytest.raises(FieldValuesError) as caught:
        parse_field_patch(READY_FIELDS, {"total": "lots", "tax": "-", "issue_date": "soon"})

    assert len(caught.value.errors) == 3


# Edits ---------------------------------------------------------------------------------------


def test_edit_records_old_and_new_values() -> None:
    invoice = invoice_in(S.NEEDS_REVIEW)
    version = invoice.version
    fields = parse_field_patch(invoice.fields, {"total": "120.50", "invoice_number": None})

    event = invoice.edit_fields(fields, actor=USER, at=at(10))

    assert event is not None
    assert event.action is AuditAction.FIELDS_EDITED
    assert event.actor == USER
    assert event.details == {
        "changes": {
            "invoice_number": {"from": "INV-1", "to": None},
            "total": {"from": "100.00", "to": "120.50"},
        }
    }
    assert invoice.fields == fields
    assert invoice.version == version + 1
    assert invoice.status is S.NEEDS_REVIEW


def test_an_edit_that_changes_nothing_records_nothing() -> None:
    invoice = invoice_in(S.NEEDS_REVIEW)
    events = invoice.events

    assert invoice.edit_fields(READY_FIELDS, actor=USER, at=at(10)) is None
    assert invoice.events == events


@pytest.mark.parametrize("status", [s for s in InvoiceStatus if s is not S.NEEDS_REVIEW])
def test_edits_are_only_allowed_in_review(status: InvoiceStatus) -> None:
    invoice = invoice_in(status)
    changed = parse_field_patch(invoice.fields, {"total": "1.00"})

    with pytest.raises(InvalidTransitionError, match="fields_edited"):
        invoice.edit_fields(changed, actor=USER, at=at(10))


@pytest.mark.parametrize("kind", [ActorKind.SYSTEM, ActorKind.AI])
def test_only_a_person_may_edit(kind: ActorKind) -> None:
    invoice = invoice_in(S.NEEDS_REVIEW)
    changed = parse_field_patch(invoice.fields, {"total": "1.00"})

    with pytest.raises(ActorNotPermittedError):
        invoice.edit_fields(changed, actor=ACTORS[kind], at=at(10))

    assert invoice.fields == READY_FIELDS


# Approval ------------------------------------------------------------------------------------


def _in_review(fields: InvoiceFields) -> Invoice:
    invoice = new_invoice(fields)
    system = ACTORS[ActorKind.SYSTEM]
    invoice.transition_to(S.EXTRACTING, actor=system, at=at(1))
    invoice.transition_to(S.NEEDS_REVIEW, actor=system, at=at(2))
    return invoice


def test_approval_lists_every_missing_required_field() -> None:
    invoice = _in_review(InvoiceFields(vendor_name="Acme", currency="EUR"))

    with pytest.raises(ApprovalBlockedError) as caught:
        invoice.transition_to(S.APPROVED, actor=USER, at=at(3))

    assert caught.value.missing == ["invoice_number", "issue_date", "total"]
    assert invoice.status is S.NEEDS_REVIEW


@pytest.mark.parametrize("missing", REQUIRED_FOR_APPROVAL)
def test_each_required_field_blocks_approval(missing: str) -> None:
    invoice = _in_review(parse_field_patch(READY_FIELDS, {missing: None}))

    with pytest.raises(ApprovalBlockedError, match=missing):
        invoice.transition_to(S.APPROVED, actor=USER, at=at(3))


def test_rejection_does_not_need_the_fields() -> None:
    invoice = _in_review(InvoiceFields())

    invoice.transition_to(S.REJECTED, actor=USER, at=at(3), reason="not an invoice")

    assert invoice.status is S.REJECTED


def test_edit_then_approve_is_replayed_by_restore() -> None:
    invoice = _in_review(InvoiceFields(vendor_name="Acme", currency="EUR"))
    completed = parse_field_patch(
        invoice.fields,
        {"invoice_number": "A-7", "issue_date": "2026-10-01", "total": "99.00"},
    )
    invoice.edit_fields(completed, actor=USER, at=at(3))
    invoice.transition_to(S.APPROVED, actor=USER, at=at(4))

    restored = Invoice.restore(
        id=invoice.id,
        filename=invoice.filename,
        uploaded_at=invoice.uploaded_at,
        fields=invoice.fields,
        events=list(invoice.events),
    )

    assert restored.events == invoice.events
    assert restored.status is S.APPROVED
    assert restored.version == 5
