from collections.abc import Callable
from uuid import UUID, uuid4

import pytest

from invoice_intake.domain import (
    ActorKind,
    ApprovalBlockedError,
    AuditAction,
    Document,
    FieldValuesError,
    InvalidInvoiceDataError,
    InvalidTransitionError,
    Invoice,
    InvoiceFields,
    InvoiceStatus,
)
from invoice_intake.services.intake import InvoiceNotFoundError
from invoice_intake.services.review import ReviewService, VersionConflictError

from .domain_helpers import ACTORS, at, invoice_in, new_invoice
from .fakes import InMemoryInvoiceRepository

S = InvoiceStatus
ALICE = ACTORS[ActorKind.USER]
PDF = Document("application/pdf", b"%PDF-1.4")


def _setup(invoice: Invoice) -> tuple[ReviewService, InMemoryInvoiceRepository]:
    repository = InMemoryInvoiceRepository()
    repository.add(invoice, PDF)
    return ReviewService(repository, clock=lambda: at(30)), repository


def _stored(repository: InMemoryInvoiceRepository, invoice_id: UUID) -> Invoice:
    stored = repository.get(invoice_id)
    assert stored is not None
    return stored


def test_edit_then_approve() -> None:
    invoice = invoice_in(S.NEEDS_REVIEW)
    service, repository = _setup(invoice)

    edited = service.edit_fields(
        invoice.id, version=invoice.version, patch={"total": "250.00"}, reviewer=ALICE
    )
    approved = service.approve(invoice.id, version=edited.version, reviewer=ALICE)

    stored = _stored(repository, invoice.id)
    assert stored.status is S.APPROVED
    assert str(stored.fields.total) == "250.00"
    assert [e.action for e in stored.events][-2:] == [
        AuditAction.FIELDS_EDITED,
        AuditAction.STATUS_CHANGED,
    ]
    assert approved.events[-1].actor == ALICE


def test_reject_records_the_reason() -> None:
    invoice = invoice_in(S.NEEDS_REVIEW)
    service, repository = _setup(invoice)

    service.reject(invoice.id, version=invoice.version, reviewer=ALICE, reason=" duplicate ")

    stored = _stored(repository, invoice.id)
    assert stored.status is S.REJECTED
    assert stored.events[-1].reason == "duplicate"


def test_a_no_op_edit_keeps_the_version() -> None:
    invoice = invoice_in(S.NEEDS_REVIEW)
    service, repository = _setup(invoice)

    result = service.edit_fields(
        invoice.id, version=invoice.version, patch={"total": "100.00"}, reviewer=ALICE
    )

    assert result.version == invoice.version
    assert _stored(repository, invoice.id).version == invoice.version


Call = Callable[[ReviewService, UUID, int], object]
CALLS: dict[str, Call] = {
    "edit": lambda s, i, v: s.edit_fields(i, version=v, patch={"total": "1.00"}, reviewer=ALICE),
    "approve": lambda s, i, v: s.approve(i, version=v, reviewer=ALICE),
    "reject": lambda s, i, v: s.reject(i, version=v, reviewer=ALICE, reason="no"),
}


@pytest.mark.parametrize("name", CALLS)
def test_a_stale_version_is_refused(name: str) -> None:
    invoice = invoice_in(S.NEEDS_REVIEW)
    service, repository = _setup(invoice)
    # A colleague edits first; our view (invoice.version) is now one behind.
    service.edit_fields(invoice.id, version=invoice.version, patch={"tax": "21.00"}, reviewer=ALICE)

    with pytest.raises(VersionConflictError, match=f"version {invoice.version + 1}, not"):
        CALLS[name](service, invoice.id, invoice.version)

    assert _stored(repository, invoice.id).status is S.NEEDS_REVIEW


@pytest.mark.parametrize("name", CALLS)
@pytest.mark.parametrize("status", [S.UPLOADED, S.EXTRACTING, S.APPROVED, S.REJECTED, S.EXPORTED])
def test_decisions_need_the_review_status(name: str, status: InvoiceStatus) -> None:
    invoice = invoice_in(status)
    service, _ = _setup(invoice)

    with pytest.raises(InvalidTransitionError):
        CALLS[name](service, invoice.id, invoice.version)


@pytest.mark.parametrize("name", CALLS)
def test_unknown_invoice_is_not_found(name: str) -> None:
    service, _ = _setup(invoice_in(S.NEEDS_REVIEW))

    with pytest.raises(InvoiceNotFoundError):
        CALLS[name](service, uuid4(), 1)


def test_rule_violations_reach_the_caller_and_store_nothing() -> None:
    blank = new_invoice(InvoiceFields())
    system = ACTORS[ActorKind.SYSTEM]
    blank.transition_to(S.EXTRACTING, actor=system, at=at(1))
    blank.transition_to(S.NEEDS_REVIEW, actor=system, at=at(2))
    service, repository = _setup(blank)
    version = blank.version

    with pytest.raises(ApprovalBlockedError):
        service.approve(blank.id, version=version, reviewer=ALICE)
    with pytest.raises(InvalidInvoiceDataError, match="reason"):
        service.reject(blank.id, version=version, reviewer=ALICE, reason="  ")
    with pytest.raises(FieldValuesError):
        service.edit_fields(blank.id, version=version, patch={"total": "x"}, reviewer=ALICE)

    assert _stored(repository, blank.id).version == version
