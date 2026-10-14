from datetime import date
from decimal import Decimal

import pytest

from invoice_intake.domain import (
    ActorKind,
    InvalidInvoiceDataError,
    Invoice,
    InvoiceFields,
    LineItem,
)

from .domain_helpers import ACTORS, at


def _item(**overrides: object) -> LineItem:
    values: dict[str, object] = {
        "description": "Consulting hours",
        "quantity": Decimal("2"),
        "unit_price": Decimal("150.00"),
        "amount": Decimal("300.00"),
    }
    values.update(overrides)
    return LineItem(**values)  # type: ignore[arg-type]


def test_valid_line_item() -> None:
    item = _item()

    assert item.amount == Decimal("300.00")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"description": "  "}, "description"),
        ({"quantity": Decimal("0")}, "quantity"),
        ({"quantity": Decimal("-1")}, "quantity"),
        ({"unit_price": Decimal("-0.01")}, "unit_price"),
        ({"amount": Decimal("NaN")}, "amount"),
        ({"amount": Decimal("Infinity")}, "amount"),
        ({"unit_price": 150.0}, "unit_price"),
        ({"quantity": 2}, "quantity"),
    ],
)
def test_invalid_line_item_is_rejected(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(InvalidInvoiceDataError, match=message):
        _item(**overrides)


def test_fields_start_empty() -> None:
    invoice = Invoice(filename="a.pdf", uploaded_by=ACTORS[ActorKind.USER], uploaded_at=at(0))

    assert invoice.fields == InvoiceFields()
    assert invoice.fields.line_items == ()
    assert invoice.fields.total is None


def test_complete_fields_are_accepted() -> None:
    fields = InvoiceFields(
        vendor_name="Acme Supplies Ltd",
        invoice_number="INV-0001",
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 31),
        currency="EUR",
        subtotal=Decimal("300.00"),
        tax=Decimal("63.00"),
        total=Decimal("363.00"),
        line_items=(_item(),),
    )

    invoice = Invoice(
        filename="a.pdf", uploaded_by=ACTORS[ActorKind.USER], uploaded_at=at(0), fields=fields
    )

    assert invoice.fields is fields


def test_totals_are_not_cross_checked() -> None:
    # A mismatch is shown to the reviewer later; it is not a reason to refuse the data.
    fields = InvoiceFields(subtotal=Decimal("100"), tax=Decimal("21"), total=Decimal("999"))

    assert fields.total == Decimal("999")


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"vendor_name": " "}, "vendor_name"),
        ({"invoice_number": ""}, "invoice_number"),
        ({"currency": "eur"}, "currency"),
        ({"currency": "EURO"}, "currency"),
        ({"total": Decimal("-1")}, "total"),
        ({"tax": 21.0}, "tax"),
        ({"issue_date": date(2026, 10, 2), "due_date": date(2026, 10, 1)}, "due_date"),
    ],
)
def test_invalid_fields_are_rejected(values: dict[str, object], message: str) -> None:
    with pytest.raises(InvalidInvoiceDataError, match=message):
        InvoiceFields(**values)  # type: ignore[arg-type]


def test_same_day_due_date_is_allowed() -> None:
    fields = InvoiceFields(issue_date=date(2026, 10, 1), due_date=date(2026, 10, 1))

    assert fields.due_date == fields.issue_date
