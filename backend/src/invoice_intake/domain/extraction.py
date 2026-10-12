"""AI extraction contract: what a provider must return, and the strict check of that output.

Every provider returns ``RawExtraction`` (the model's parsed JSON, untrusted). ``parse_extraction``
turns it into an ``ExtractionResult`` or raises ``ExtractionOutputError`` listing every problem,
so all providers share one validation path and every rejection can be recorded.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from .errors import DomainError
from .invoice import InvoiceFields, LineItem
from .repository import Document

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
_TEXT_FIELDS = ("vendor_name", "invoice_number", "currency")
_DATE_FIELDS = ("issue_date", "due_date")
_MONEY_FIELDS = ("subtotal", "tax", "total")
_LINE_KEYS = ("description", "quantity", "unit_price", "amount")
_DECIMAL = re.compile(r"^-?\d+(\.\d+)?$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_NULLABLE_STRING: dict[str, Any] = {"type": ["string", "null"]}
_DECIMAL_HINT = "Plain decimal with a dot and no thousands separators, e.g. 1234.50."

# The JSON schema providers must follow (OpenAI strict structured-output compatible: every key
# required, no extra keys, nullable values instead of optional ones).
OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["fields", "confidence"],
    "properties": {
        "fields": {
            "type": "object",
            "additionalProperties": False,
            "required": list(FIELD_NAMES),
            "properties": {
                "vendor_name": {**_NULLABLE_STRING, "description": "Seller's legal name."},
                "invoice_number": {**_NULLABLE_STRING, "description": "As printed."},
                "issue_date": {**_NULLABLE_STRING, "description": "ISO date YYYY-MM-DD."},
                "due_date": {**_NULLABLE_STRING, "description": "ISO date YYYY-MM-DD."},
                "currency": {**_NULLABLE_STRING, "description": "ISO 4217 code, e.g. EUR."},
                "subtotal": {**_NULLABLE_STRING, "description": _DECIMAL_HINT},
                "tax": {**_NULLABLE_STRING, "description": _DECIMAL_HINT},
                "total": {**_NULLABLE_STRING, "description": _DECIMAL_HINT},
                "line_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": list(_LINE_KEYS),
                        "properties": {
                            key: {"type": "string", "description": _DECIMAL_HINT}
                            if key != "description"
                            else {"type": "string"}
                            for key in _LINE_KEYS
                        },
                    },
                },
            },
        },
        "confidence": {
            "type": "object",
            "additionalProperties": False,
            "required": list(FIELD_NAMES),
            "properties": {
                name: {"type": "number", "description": "0 to 1: how sure the value is right."}
                for name in FIELD_NAMES
            },
        },
    },
}


class ExtractionOutputError(DomainError):
    """The provider's output does not match the contract. ``errors`` lists every problem."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


class ExtractionProviderError(DomainError):
    """The provider could not produce any output (network, API or configuration trouble)."""


@dataclass(frozen=True)
class RawExtraction:
    provider: str
    model: str
    output: object  # parsed JSON, or the raw text when the reply was not JSON


@dataclass(frozen=True)
class ExtractionResult:
    provider: str
    model: str
    fields: InvoiceFields
    confidence: Mapping[str, float]  # one value in [0, 1] per name in FIELD_NAMES


class ExtractionProvider(Protocol):
    name: str

    def extract(self, document: Document) -> RawExtraction:
        """Read the document. Raises ``ExtractionProviderError`` if no output was produced."""
        ...


def parse_extraction(raw: RawExtraction) -> ExtractionResult:
    errors: list[str] = []
    top = _exact_object(raw.output, ("fields", "confidence"), "output", errors)
    if top is None:
        raise ExtractionOutputError(errors)
    fields = _parse_fields(top["fields"], errors)
    confidence = _parse_confidence(top["confidence"], errors)
    if errors or fields is None or confidence is None:
        raise ExtractionOutputError(errors)
    return ExtractionResult(raw.provider, raw.model, fields, confidence)


def empty_output() -> dict[str, Any]:
    """Valid output for a document where nothing could be read: all empty, zero confidence."""
    fields: dict[str, Any] = {name: None for name in FIELD_NAMES}
    fields["line_items"] = []
    return {"fields": fields, "confidence": {name: 0.0 for name in FIELD_NAMES}}


def _exact_object(
    value: object, keys: tuple[str, ...], where: str, errors: list[str]
) -> dict[str, Any] | None:
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


def _parse_fields(value: object, errors: list[str]) -> InvoiceFields | None:
    data = _exact_object(value, FIELD_NAMES, "fields", errors)
    if data is None:
        return None
    before = len(errors)
    parsed: dict[str, Any] = {}
    for name in _TEXT_FIELDS:
        parsed[name] = _text(data[name], f"fields.{name}", errors)
    for name in _DATE_FIELDS:
        parsed[name] = _date(data[name], f"fields.{name}", errors)
    for name in _MONEY_FIELDS:
        parsed[name] = _decimal(data[name], f"fields.{name}", errors, nullable=True)
    parsed["line_items"] = _line_items(data["line_items"], errors)
    if len(errors) > before:
        return None
    try:
        return InvoiceFields(**parsed)
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
        line = _exact_object(raw, _LINE_KEYS, where, errors)
        if line is None:
            continue
        description = _text(line["description"], f"{where}.description", errors)
        numbers = [
            _decimal(line[key], f"{where}.{key}", errors, nullable=False)
            for key in ("quantity", "unit_price", "amount")
        ]
        if description is None or None in numbers:
            continue
        quantity, unit_price, amount = numbers
        assert quantity is not None and unit_price is not None and amount is not None
        try:
            items.append(LineItem(description, quantity, unit_price, amount))
        except DomainError as error:
            errors.append(f"{where}: {error}")
    return tuple(items)


def _parse_confidence(value: object, errors: list[str]) -> dict[str, float] | None:
    data = _exact_object(value, FIELD_NAMES, "confidence", errors)
    if data is None:
        return None
    confidence: dict[str, float] = {}
    for name in FIELD_NAMES:
        number = data[name]
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            errors.append(f"confidence.{name} must be a number")
        elif not 0 <= number <= 1:
            errors.append(f"confidence.{name} must be between 0 and 1")
        else:
            confidence[name] = float(number)
    return confidence if len(confidence) == len(FIELD_NAMES) else None


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
    try:
        return Decimal(value.strip())
    except InvalidOperation:  # pragma: no cover - the pattern already guarantees a decimal
        errors.append(f"{where} is not a decimal")
        return None
