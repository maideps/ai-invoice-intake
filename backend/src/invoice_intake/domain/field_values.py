"""The JSON form of invoice fields, and its strict parsing.

One format everywhere: decimals as plain strings ("1234.50"), dates as ISO strings, ``null`` for
an empty value, line items as a list. AI extraction output and reviewer edits both use it, so
both pass the same checks. Parsers collect every problem instead of stopping at the first.
"""

import re
from datetime import date
from decimal import Decimal
from typing import Any

from .errors import DomainError, InvalidInvoiceDataError
from .invoice import InvoiceFields, LineItem

FIELD_NAMES = (
    "vendor_name",
    "invoice_number",
    "issue_date",
    "due_date",
    "currency",
    "subtotal",
    "tax",
    "total",
    "line_items",
)
TEXT_FIELDS = ("vendor_name", "invoice_number", "currency")
DATE_FIELDS = ("issue_date", "due_date")
MONEY_FIELDS = ("subtotal", "tax", "total")
LINE_KEYS = ("description", "quantity", "unit_price", "amount")
_DECIMAL = re.compile(r"^-?\d+(\.\d+)?$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FieldValuesError(InvalidInvoiceDataError):
    """Field values in JSON form are malformed. ``errors`` lists every problem."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def parse_fields(value: object, errors: list[str]) -> InvoiceFields | None:
    """A complete set of fields (every key present). Appends problems to ``errors``."""
    data = exact_object(value, FIELD_NAMES, "fields", errors)
    if data is None:
        return None
    return _build({}, data, errors)


def parse_field_patch(current: InvoiceFields, patch: object) -> InvoiceFields:
    """``current`` with the fields named in ``patch`` replaced (``null`` clears a field).

    Raises ``FieldValuesError`` listing every problem, including unknown field names and
    rule violations of the resulting fields (for example a due date before the issue date).
    """
    errors: list[str] = []
    if not isinstance(patch, dict) or not patch:
        raise FieldValuesError(["fields must be a non-empty JSON object"])
    unknown = sorted(str(key) for key in patch if key not in FIELD_NAMES)
    if unknown:
        raise FieldValuesError([f"fields has unknown keys {', '.join(unknown)}"])
    base = {name: getattr(current, name) for name in FIELD_NAMES}
    fields = _build(base, patch, errors)
    if fields is None:
        raise FieldValuesError(errors)
    return fields


def exact_object(
    value: object, keys: tuple[str, ...], where: str, errors: list[str]
) -> dict[str, Any] | None:
    """``value`` if it is a JSON object with exactly ``keys``; otherwise record why not."""
    if not isinstance(value, dict):
        errors.append(f"{where} must be a JSON object")
        return None
    missing = [key for key in keys if key not in value]
    unknown = sorted(str(key) for key in value if key not in keys)
    if missing:
        errors.append(f"{where} is missing {', '.join(missing)}")
    if unknown:
        errors.append(f"{where} has unknown keys {', '.join(unknown)}")
    return None if missing or unknown else value


def _build(base: dict[str, Any], data: dict[str, Any], errors: list[str]) -> InvoiceFields | None:
    before = len(errors)
    values = dict(base)
    for name in data:
        where = f"fields.{name}"
        if name in TEXT_FIELDS:
            values[name] = _text(data[name], where, errors)
        elif name in DATE_FIELDS:
            values[name] = _date(data[name], where, errors)
        elif name in MONEY_FIELDS:
            values[name] = _decimal(data[name], where, errors, nullable=True)
        else:
            values[name] = _line_items(data[name], errors)
    if len(errors) > before:
        return None
    try:
        return InvoiceFields(**values)
    except DomainError as error:  # cross-field and value rules, e.g. due date before issue date
        errors.append(f"fields: {error}")
        return None


def _line_items(value: object, errors: list[str]) -> tuple[LineItem, ...]:
    if not isinstance(value, list):
        errors.append("fields.line_items must be a list")
        return ()
    items: list[LineItem] = []
    for index, raw in enumerate(value):
        where = f"fields.line_items[{index}]"
        line = exact_object(raw, LINE_KEYS, where, errors)
        if line is None:
            continue
        description = _text(line["description"], f"{where}.description", errors)
        quantity, unit_price, amount = (
            _decimal(line[key], f"{where}.{key}", errors, nullable=False)
            for key in ("quantity", "unit_price", "amount")
        )
        if description is None or quantity is None or unit_price is None or amount is None:
            continue
        try:
            items.append(LineItem(description, quantity, unit_price, amount))
        except DomainError as error:
            errors.append(f"{where}: {error}")
    return tuple(items)


def _text(value: object, where: str, errors: list[str]) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{where} must be a non-empty string or null")
        return None
    return value.strip()


def _date(value: object, where: str, errors: list[str]) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _ISO_DATE.match(value):
        errors.append(f"{where} must be an ISO date (YYYY-MM-DD) or null")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{where} is not a real date")
        return None


def _decimal(value: object, where: str, errors: list[str], *, nullable: bool) -> Decimal | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not _DECIMAL.match(value.strip()):
        errors.append(f"{where} must be a decimal string like '1234.50'")
        return None
    return Decimal(value.strip())
