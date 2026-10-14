# Synthetic invoices

Generated test data. Every vendor, customer, address and amount is invented; each PDF says so in its footer.

`invoices/` holds the default set (seed 42, 12 invoices). For each invoice:

- `invoice-NNN.pdf` — the document, in one of three layouts (`classic`, `banner`, `compact`), in English, German, French or Norwegian, priced in USD, EUR, GBP, CAD or NOK.
- `invoice-NNN.json` — the ground truth: the values an extractor should read from the PDF.

## Ground-truth format (schema version 1)

```json
{
  "schema_version": 1,
  "file": "invoice-001.pdf",
  "layout": "classic",
  "fields": {
    "vendor_name": "Maple Ridge Software Inc.",
    "invoice_number": "MRS-04591",
    "issue_date": "2026-06-01",
    "due_date": "2026-07-16",
    "currency": "CAD",
    "subtotal": "5637.93",
    "tax": "732.93",
    "total": "6370.86",
    "line_items": [
      { "description": "Team plan subscription, 10 seats", "quantity": "12", "unit_price": "359.71", "amount": "4316.52" }
    ]
  }
}
```

- Money is a decimal string with two places; dates are ISO `YYYY-MM-DD`; quantities are decimal strings.
- Amounts add up: line amount = quantity x unit price (rounded half up to cents), subtotal = sum of line amounts, total = subtotal + tax.
- Dates and numbers in the PDF are printed in the vendor's local format (for example `14.02.2026` and `3 627,23 €`); the ground truth is always normalised.
- `repositories/backend/tools/samplegen/ground_truth.py` (`load_ground_truth`) validates a document strictly: missing or unknown keys, floats and malformed dates are errors.

## Regenerating

```bash
npm run samples
```

The output is byte-identical on every machine for the same seed and ReportLab version (pinned in `repositories/backend/pyproject.toml`). A backend test fails if these files drift from the generator, so regenerate and commit them together with any generator change. For a different or larger set, run the generator directly from `repositories/backend/`: `python tools/generate_samples.py --seed 7 --count 30 --out /tmp/invoices`.
