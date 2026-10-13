"""AI extraction contract: what a provider must return, and the strict check of that output.

Every provider returns ``RawExtraction`` (the model's parsed JSON, untrusted). ``parse_extraction``
turns it into an ``ExtractionResult`` or raises ``ExtractionOutputError`` listing every problem,
so all providers share one validation path and every rejection can be recorded. Field values use
the JSON form in ``field_values``, the same one reviewers edit with.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .errors import DomainError
from .field_values import FIELD_NAMES, LINE_KEYS, exact_object, parse_fields
from .invoice import InvoiceFields
from .repository import Document

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
                        "required": list(LINE_KEYS),
                        "properties": {
                            key: {"type": "string", "description": _DECIMAL_HINT}
                            if key != "description"
                            else {"type": "string"}
                            for key in LINE_KEYS
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
    top = exact_object(raw.output, ("fields", "confidence"), "output", errors)
    if top is None:
        raise ExtractionOutputError(errors)
    fields = parse_fields(top["fields"], errors)
    confidence = _parse_confidence(top["confidence"], errors)
    if errors or fields is None or confidence is None:
        raise ExtractionOutputError(errors)
    return ExtractionResult(raw.provider, raw.model, fields, confidence)


def empty_output() -> dict[str, Any]:
    """Valid output for a document where nothing could be read: all empty, zero confidence."""
    fields: dict[str, Any] = {name: None for name in FIELD_NAMES}
    fields["line_items"] = []
    return {"fields": fields, "confidence": {name: 0.0 for name in FIELD_NAMES}}


def _parse_confidence(value: object, errors: list[str]) -> dict[str, float] | None:
    data = exact_object(value, FIELD_NAMES, "confidence", errors)
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
