import copy
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from invoice_intake.domain import (
    FIELD_NAMES,
    OUTPUT_SCHEMA,
    ExtractionOutputError,
    InvoiceFields,
    RawExtraction,
    empty_output,
    parse_extraction,
)

SAMPLE = Path(__file__).resolve().parents[3] / "samples" / "invoices" / "invoice-003.json"


def _valid() -> dict[str, Any]:
    fields = json.loads(SAMPLE.read_text(encoding="utf-8"))["fields"]
    return {"fields": fields, "confidence": {name: 0.9 for name in FIELD_NAMES}}


def _parse(output: object) -> InvoiceFields:
    return parse_extraction(RawExtraction("test", "m", output)).fields


def test_schema_and_parser_agree_on_the_field_names() -> None:
    properties = OUTPUT_SCHEMA["properties"]
    assert properties["fields"]["required"] == list(FIELD_NAMES)
    assert properties["confidence"]["required"] == list(FIELD_NAMES)
    assert OUTPUT_SCHEMA["additionalProperties"] is False


def test_ground_truth_shaped_output_is_accepted() -> None:
    result = parse_extraction(RawExtraction("test", "m", _valid()))

    assert result.fields.vendor_name == "Kestrel Analytik GmbH"
    assert result.fields.line_items
    assert result.confidence == {name: 0.9 for name in FIELD_NAMES}
    assert (result.provider, result.model) == ("test", "m")


def test_empty_output_is_valid_and_empty() -> None:
    assert _parse(empty_output()) == InvoiceFields()


def test_any_plain_decimal_is_accepted_and_whitespace_trimmed() -> None:
    output = _valid()
    output["fields"]["total"] = " 10689.3 "
    output["fields"]["vendor_name"] = "  Kestrel Analytik GmbH "

    fields = _parse(output)

    assert fields.total == Decimal("10689.3")
    assert fields.vendor_name == "Kestrel Analytik GmbH"


def test_integer_confidence_is_accepted() -> None:
    output = _valid()
    output["confidence"]["total"] = 1

    assert parse_extraction(RawExtraction("t", "m", output)).confidence["total"] == 1.0


def _broken(change: str) -> object:
    output = copy.deepcopy(_valid())
    fields, confidence = output["fields"], output["confidence"]
    line = fields["line_items"][0]
    changes: dict[str, Any] = {
        "not an object": lambda: "Sure! Here is the invoice data...",
        "missing top key": lambda: output.pop("confidence"),
        "extra top key": lambda: output.update(notes="hi"),
        "missing field": lambda: fields.pop("due_date"),
        "extra field": lambda: fields.update(iban="DE00"),
        "localised amount": lambda: fields.update(total="10.689,25"),
        "currency symbol": lambda: fields.update(subtotal="€8982.56"),
        "number not string": lambda: fields.update(tax=1706.69),
        "non-ISO date": lambda: fields.update(issue_date="07.08.2026"),
        "impossible date": lambda: fields.update(due_date="2026-02-30"),
        "blank text": lambda: fields.update(vendor_name="   "),
        "bad currency": lambda: fields.update(currency="Euro"),
        "due before issue": lambda: fields.update(issue_date="2026-09-01"),
        "negative total": lambda: fields.update(total="-1.00"),
        "line items not a list": lambda: fields.update(line_items={"a": 1}),
        "line item extra key": lambda: line.update(vat="19"),
        "line item null amount": lambda: line.update(amount=None),
        "zero quantity": lambda: line.update(quantity="0"),
        "confidence too high": lambda: confidence.update(total=1.5),
        "confidence negative": lambda: confidence.update(tax=-0.1),
        "confidence text": lambda: confidence.update(currency="high"),
        "confidence boolean": lambda: confidence.update(currency=True),
        "confidence missing": lambda: confidence.pop("line_items"),
    }
    result = changes[change]()
    return result if change == "not an object" else output


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("not an object", "output must be a JSON object"),
        ("missing top key", "output is missing confidence"),
        ("extra top key", "output has unknown keys notes"),
        ("missing field", "fields is missing due_date"),
        ("extra field", "fields has unknown keys iban"),
        ("localised amount", "fields.total must be a decimal string"),
        ("currency symbol", "fields.subtotal must be a decimal string"),
        ("number not string", "fields.tax must be a decimal string"),
        ("non-ISO date", "fields.issue_date must be an ISO date"),
        ("impossible date", "fields.due_date is not a real date"),
        ("blank text", "fields.vendor_name must be a non-empty string"),
        ("bad currency", "currency must be a three-letter ISO 4217 code"),
        ("due before issue", "due_date must not be before issue_date"),
        ("negative total", "total must not be negative"),
        ("line items not a list", "fields.line_items must be a list"),
        ("line item extra key", r"fields.line_items\[0\] has unknown keys vat"),
        ("line item null amount", r"fields.line_items\[0\].amount must be a decimal string"),
        ("zero quantity", r"fields.line_items\[0\]: quantity must be greater than zero"),
        ("confidence too high", "confidence.total must be between 0 and 1"),
        ("confidence negative", "confidence.tax must be between 0 and 1"),
        ("confidence text", "confidence.currency must be a number"),
        ("confidence boolean", "confidence.currency must be a number"),
        ("confidence missing", "confidence is missing line_items"),
    ],
)
def test_invalid_output_is_rejected_with_a_reason(change: str, message: str) -> None:
    with pytest.raises(ExtractionOutputError, match=message):
        _parse(_broken(change))


def test_every_problem_is_reported_at_once() -> None:
    output = _valid()
    output["fields"]["total"] = "lots"
    output["fields"]["issue_date"] = "yesterday"
    output["confidence"]["tax"] = 7

    with pytest.raises(ExtractionOutputError) as caught:
        _parse(output)

    assert len(caught.value.errors) == 3
