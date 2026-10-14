"""Build one synthetic invoice from a seed and an index, as valid domain data."""

import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from invoice_intake.domain import InvoiceFields, LineItem

from .catalog import CUSTOMERS, VENDORS, Customer, Item, Vendor

Layout = Literal["classic", "banner", "compact"]
LAYOUTS: tuple[Layout, ...] = ("classic", "banner", "compact")

CENT = Decimal("0.01")
FIRST_ISSUE_DATE = date(2026, 1, 5)
ISSUE_DATE_SPAN_DAYS = 270
MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)  # fmt: skip


@dataclass(frozen=True)
class Sample:
    name: str
    layout: Layout
    vendor: Vendor
    customer: Customer
    fields: InvoiceFields

    @property
    def pdf_name(self) -> str:
        return f"{self.name}.pdf"

    @property
    def json_name(self) -> str:
        return f"{self.name}.json"


def build_sample(seed: int, index: int) -> Sample:
    """Invoice number ``index`` (from 0) of the set for ``seed``; independent of the set size."""
    # Vendors and layouts cycle (7 and 3 are coprime), so any 7 or more invoices cover every
    # vendor and every layout; the seed decides the vendor order and all the values.
    order = list(VENDORS)
    random.Random(f"invoice-intake:{seed}:vendors").shuffle(order)
    vendor = order[index % len(order)]
    layout = LAYOUTS[index % len(LAYOUTS)]
    rng = random.Random(f"invoice-intake:{seed}:{index}")

    customer = rng.choice(CUSTOMERS)
    issue_date = FIRST_ISSUE_DATE + timedelta(days=rng.randint(0, ISSUE_DATE_SPAN_DAYS))
    line_items = tuple(
        _line_item(rng, item)
        for item in rng.sample(vendor.items, rng.randint(1, len(vendor.items)))
    )
    subtotal = sum((line.amount for line in line_items), Decimal("0.00"))
    tax = (subtotal * vendor.tax_rate).quantize(CENT, rounding=ROUND_HALF_UP)

    fields = InvoiceFields(
        vendor_name=vendor.name,
        invoice_number=vendor.number_pattern.format(year=issue_date.year, n=rng.randint(1, 9999)),
        issue_date=issue_date,
        due_date=issue_date + timedelta(days=vendor.payment_days),
        currency=vendor.currency,
        subtotal=subtotal,
        tax=tax,
        total=subtotal + tax,
        line_items=line_items,
    )
    return Sample(
        name=f"invoice-{index + 1:03d}",
        layout=layout,
        vendor=vendor,
        customer=customer,
        fields=fields,
    )


def _line_item(rng: random.Random, item: Item) -> LineItem:
    if item.unit == "h":
        quantity = Decimal(rng.randint(2, 48)) / 2  # half hours
    elif item.unit == "month":
        quantity = Decimal(rng.randint(1, 12))
    else:
        quantity = Decimal(rng.randint(1, 20))
    cents = rng.randint(int(item.min_price * 100), int(item.max_price * 100))
    unit_price = (Decimal(cents) / 100).quantize(CENT)
    return LineItem(
        description=item.description,
        quantity=quantity,
        unit_price=unit_price,
        amount=(quantity * unit_price).quantize(CENT, rounding=ROUND_HALF_UP),
    )


def format_date(value: date, pattern: str) -> str:
    """``strftime`` with English month names that do not depend on the machine's locale."""
    return value.strftime(pattern.replace("%B", MONTHS[value.month - 1]))


def format_number(value: Decimal, vendor: Vendor, places: int = 2) -> str:
    """Format with the vendor's decimal and thousands separators."""
    text = f"{value:,.{places}f}"
    style = vendor.numbers
    return text.replace(",", "\0").replace(".", style.decimal_sep).replace("\0", style.group_sep)


def format_quantity(value: Decimal, vendor: Vendor) -> str:
    places = 0 if value == value.to_integral_value() else 1
    return format_number(value, vendor, places)


def format_money(value: Decimal, vendor: Vendor) -> str:
    number = format_number(value, vendor)
    if vendor.symbol_after:
        return f"{number} {vendor.currency_symbol}"
    return f"{vendor.currency_symbol}{number}"
