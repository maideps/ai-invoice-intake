"""Ground-truth JSON: the values an extractor should read from each sample PDF.

Money is a decimal string with two places and dates are ISO strings, so nothing passes
through a float. ``load_ground_truth`` is strict: unknown or missing keys are errors.
"""

import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from invoice_intake.domain import DomainError, InvoiceFields, LineItem

from .builder import LAYOUTS, Sample

SCHEMA_VERSION = 1

_MONEY = re.compile(r"^\d+\.\d{2}$")
_QUANTITY = re.compile(r"^\d+(\.\d+)?$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TOP_KEYS = {"schema_version", "file", "layout", "fields"}
_FIELD_KEYS = {
    "vendor_name",
    "invoice_number",
    "issue_date",
    "due_date",
    "currency",
    "subtotal",
    "tax",
    "total",
    "line_items",
}
_LINE_KEYS = {"description", "quantity", "unit_price", "amount"}


class GroundTruthError(ValueError):
    """A ground-truth document does not match the schema."""


@dataclass(frozen=True)
class GroundTruth:
    file: str
    layout: str
    fields: InvoiceFields


def to_document(sample: Sample) -> dict[str, Any]:
    fields = sample.fields
    assert fields.issue_date and fields.due_date  # always set by the builder
    return {
        "schema_version": SCHEMA_VERSION,
        "file": sample.pdf_name,
        "layout": sample.layout,
        "fields": {
            "vendor_name": fields.vendor_name,
            "invoice_number": fields.invoice_number,
            "issue_date": fields.issue_date.isoformat(),
            "due_date": fields.due_date.isoformat(),
            "currency": fields.currency,
            "subtotal": str(fields.subtotal),
            "tax": str(fields.tax),
            "total": str(fields.total),
            "line_items": [
                {
                    "description": line.description,
                    "quantity": str(line.quantity),
                    "unit_price": str(line.unit_price),
                    "amount": str(line.amount),
                }
                for line in fields.line_items
            ],
        },
    }


def dumps(sample: Sample) -> bytes:
    """Serialised with ``\\n`` line endings and UTF-8, the same on every OS."""
    return (json.dumps(to_document(sample), indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def load_ground_truth(document: object) -> GroundTruth:
    """Validate a parsed ground-truth document and return it as domain data."""
    top = _object(document, _TOP_KEYS, "document")
    version = top["schema_version"]
    if type(version) is not int or version != SCHEMA_VERSION:  # bool is an int subclass
        raise GroundTruthError(f"schema_version must be {SCHEMA_VERSION}")
    layout = _string(top["layout"], "layout")
    if layout not in LAYOUTS:
        raise GroundTruthError(f"layout must be one of {', '.join(LAYOUTS)}")
    fields = _object(top["fields"], _FIELD_KEYS, "fields")
    raw_lines = fields["line_items"]
    if not isinstance(raw_lines, list) or not raw_lines:
        raise GroundTruthError("line_items must be a non-empty list")
    try:
        lines = tuple(_line_item(raw, i) for i, raw in enumerate(raw_lines))
        invoice_fields = InvoiceFields(
            vendor_name=_string(fields["vendor_name"], "vendor_name"),
            invoice_number=_string(fields["invoice_number"], "invoice_number"),
            issue_date=_date(fields["issue_date"], "issue_date"),
            due_date=_date(fields["due_date"], "due_date"),
            currency=_string(fields["currency"], "currency"),
            subtotal=_decimal(fields["subtotal"], "subtotal", _MONEY),
            tax=_decimal(fields["tax"], "tax", _MONEY),
            total=_decimal(fields["total"], "total", _MONEY),
            line_items=lines,
        )
    except DomainError as error:
        raise GroundTruthError(str(error)) from error
    return GroundTruth(file=_string(top["file"], "file"), layout=layout, fields=invoice_fields)


def _line_item(raw: object, index: int) -> LineItem:
    where = f"line_items[{index}]"
    line = _object(raw, _LINE_KEYS, where)
    return LineItem(
        description=_string(line["description"], f"{where}.description"),
        quantity=_decimal(line["quantity"], f"{where}.quantity", _QUANTITY),
        unit_price=_decimal(line["unit_price"], f"{where}.unit_price", _MONEY),
        amount=_decimal(line["amount"], f"{where}.amount", _MONEY),
    )


def _object(value: object, keys: set[str], where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise GroundTruthError(f"{where} must be an object")
    missing, unknown = keys - value.keys(), value.keys() - keys
    if missing:
        raise GroundTruthError(f"{where} is missing {', '.join(sorted(missing))}")
    if unknown:
        raise GroundTruthError(f"{where} has unknown keys {', '.join(sorted(unknown))}")
    return value


def _string(value: object, where: str) -> str:
    if not isinstance(value, str):
        raise GroundTruthError(f"{where} must be a string")
    return value


def _decimal(value: object, where: str, pattern: re.Pattern[str]) -> Decimal:
    if not isinstance(value, str) or not pattern.match(value):
        raise GroundTruthError(f"{where} must be a decimal string like '12.50'")
    return Decimal(value)


def _date(value: object, where: str) -> date:
    if not isinstance(value, str) or not _DATE.match(value):
        raise GroundTruthError(f"{where} must be an ISO date (YYYY-MM-DD)")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise GroundTruthError(f"{where} is not a real date") from error
