"""Deterministic provider for tests, CI and demos: it "reads" a document by looking it up.

A document is recognised by its SHA-256 among the synthetic samples (``samples/invoices``); the
answer is that sample's ground truth with stable, varied per-field confidence. Any other
document gets empty fields and zero confidence, for a reviewer to fill in. Its output goes
through the same validation as a real model's.
"""

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from invoice_intake.domain import FIELD_NAMES, Document, RawExtraction, empty_output

MODEL = "ground-truth"


class FakeExtractionProvider:
    name = "fake"

    def __init__(self, samples_dir: Path) -> None:
        self._fields_by_digest: dict[str, dict[str, Any]] = {}
        for truth_path in sorted(samples_dir.glob("*.json")):
            truth = json.loads(truth_path.read_text(encoding="utf-8"))
            pdf = samples_dir / truth["file"]
            if pdf.is_file():
                digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
                self._fields_by_digest[digest] = truth["fields"]

    @property
    def known_documents(self) -> int:
        return len(self._fields_by_digest)

    def extract(self, document: Document) -> RawExtraction:
        fields = self._fields_by_digest.get(document.sha256)
        if fields is None:
            return RawExtraction(self.name, MODEL, empty_output())
        output = {
            "fields": copy.deepcopy(fields),
            "confidence": {name: _confidence(document.sha256, name) for name in FIELD_NAMES},
        }
        return RawExtraction(self.name, MODEL, output)


def _confidence(digest: str, field: str) -> float:
    """Between 0.55 and 0.99, fixed per document and field, so demos show some low values."""
    value = int(hashlib.sha256(f"{digest}:{field}".encode()).hexdigest()[:4], 16)
    return round(0.55 + (value % 45) / 100, 2)
