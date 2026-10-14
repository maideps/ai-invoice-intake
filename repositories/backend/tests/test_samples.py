import copy
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import pytest
from samplegen.builder import LAYOUTS, build_sample
from samplegen.catalog import VENDORS
from samplegen.generate import DEFAULT_COUNT, DEFAULT_SEED, generate
from samplegen.ground_truth import GroundTruthError, load_ground_truth, to_document

COMMITTED = Path(__file__).resolve().parents[3] / "samples" / "invoices"
CENT = Decimal("0.01")


def _files(directory: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in sorted(directory.iterdir())}


@pytest.fixture(scope="module")
def default_set(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("default")
    generate(out, seed=DEFAULT_SEED, count=DEFAULT_COUNT)
    return out


def test_same_seed_gives_identical_files(default_set: Path, tmp_path: Path) -> None:
    generate(tmp_path, seed=DEFAULT_SEED, count=DEFAULT_COUNT)

    assert _files(tmp_path) == _files(default_set)


def test_different_seed_gives_different_invoices(default_set: Path, tmp_path: Path) -> None:
    generate(tmp_path, seed=DEFAULT_SEED + 1, count=DEFAULT_COUNT)

    ours = _files(tmp_path)
    theirs = _files(default_set)
    assert ours.keys() == theirs.keys()
    assert all(ours[name] != theirs[name] for name in ours if name.endswith(".json"))


def test_an_invoice_does_not_depend_on_the_set_size(tmp_path: Path) -> None:
    generate(tmp_path / "three", seed=9, count=3)
    generate(tmp_path / "eight", seed=9, count=8)

    three, eight = _files(tmp_path / "three"), _files(tmp_path / "eight")
    assert {name: eight[name] for name in three} == three


def test_every_ground_truth_file_is_valid_and_adds_up(default_set: Path) -> None:
    documents = sorted(default_set.glob("invoice-*.json"))
    assert len(documents) == DEFAULT_COUNT

    for path in documents:
        truth = load_ground_truth(json.loads(path.read_text(encoding="utf-8")))
        fields = truth.fields
        assert truth.file == path.with_suffix(".pdf").name
        assert (default_set / truth.file).is_file()
        assert fields.line_items
        for line in fields.line_items:
            # Commercial rounding (half up), not Python's default banker's rounding.
            expected = (line.quantity * line.unit_price).quantize(CENT, rounding=ROUND_HALF_UP)
            assert line.amount == expected
        assert fields.subtotal == sum(line.amount for line in fields.line_items)
        assert fields.subtotal is not None and fields.tax is not None
        assert fields.total == fields.subtotal + fields.tax
        assert fields.issue_date and fields.due_date and fields.due_date > fields.issue_date


def test_every_pdf_is_a_pdf_with_its_number_and_the_synthetic_marker(default_set: Path) -> None:
    for path in sorted(default_set.glob("invoice-*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        pdf = (default_set / document["file"]).read_bytes()
        assert pdf.startswith(b"%PDF-")
        assert pdf.rstrip().endswith(b"%%EOF")
        assert document["fields"]["invoice_number"].encode("ascii") in pdf
        assert b"SYNTHETIC SAMPLE" in pdf


def test_default_set_is_varied(default_set: Path) -> None:
    documents = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(default_set.glob("invoice-*.json"))
    ]

    assert {d["layout"] for d in documents} == set(LAYOUTS)
    assert {d["fields"]["vendor_name"] for d in documents} == {v.name for v in VENDORS}
    assert {d["fields"]["currency"] for d in documents} == {"USD", "EUR", "GBP", "CAD", "NOK"}


def test_generate_replaces_old_samples_but_keeps_other_files(tmp_path: Path) -> None:
    generate(tmp_path, seed=1, count=5)
    (tmp_path / "notes.txt").write_text("keep me", encoding="utf-8")

    generate(tmp_path, seed=1, count=2)

    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "invoice-001.json",
        "invoice-001.pdf",
        "invoice-002.json",
        "invoice-002.pdf",
        "notes.txt",
    ]


def test_count_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="count"):
        generate(tmp_path, count=0)


def test_committed_samples_match_the_generator(default_set: Path) -> None:
    committed = {
        name: data for name, data in _files(COMMITTED).items() if name.startswith("invoice-")
    }

    assert committed.keys() == _files(default_set).keys(), "run: npm run samples"
    for name, data in _files(default_set).items():
        assert committed[name] == data, f"{name} is out of date; run: npm run samples"


# Strict loader -------------------------------------------------------------------------------


def _valid() -> dict[str, Any]:
    return to_document(build_sample(DEFAULT_SEED, 0))


def test_loader_accepts_a_generated_document() -> None:
    truth = load_ground_truth(_valid())

    assert truth.layout in LAYOUTS
    assert truth.fields == build_sample(DEFAULT_SEED, 0).fields


def _broken(change: str) -> dict[str, Any]:
    document = copy.deepcopy(_valid())
    fields = document["fields"]
    line = fields["line_items"][0]
    if change == "missing key":
        del fields["total"]
    elif change == "unknown key":
        fields["confidence"] = 0.9
    elif change == "float money":
        fields["total"] = 12.5
    elif change == "money without cents":
        fields["subtotal"] = "12.5"
    elif change == "negative money":
        fields["tax"] = "-1.00"
    elif change == "bad date":
        fields["issue_date"] = "2026-02-30"
    elif change == "non-ISO date":
        fields["due_date"] = "30/03/2026"
    elif change == "schema version":
        document["schema_version"] = 2
    elif change == "boolean version":
        document["schema_version"] = True
    elif change == "unknown layout":
        document["layout"] = "fancy"
    elif change == "empty line items":
        fields["line_items"] = []
    elif change == "line item key":
        del line["amount"]
    elif change == "line item quantity":
        line["quantity"] = "two"
    elif change == "domain rule":
        fields["currency"] = "euro"
    elif change == "not an object":
        return ["not", "an", "object"]  # type: ignore[return-value]
    return document


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("missing key", "missing total"),
        ("unknown key", "unknown keys confidence"),
        ("float money", "total must be a decimal string"),
        ("money without cents", "subtotal must be a decimal string"),
        ("negative money", "tax must be a decimal string"),
        ("bad date", "issue_date is not a real date"),
        ("non-ISO date", "due_date must be an ISO date"),
        ("schema version", "schema_version"),
        ("boolean version", "schema_version"),
        ("unknown layout", "layout"),
        ("empty line items", "line_items must be a non-empty list"),
        ("line item key", r"line_items\[0\] is missing amount"),
        ("line item quantity", r"line_items\[0\]\.quantity"),
        ("domain rule", "currency"),
        ("not an object", "document must be an object"),
    ],
)
def test_loader_rejects_malformed_documents(change: str, message: str) -> None:
    with pytest.raises(GroundTruthError, match=message):
        load_ground_truth(_broken(change))
