"""OpenAI provider: the Responses API with a strict JSON-schema output format.

PDFs are sent as ``input_file`` and PNG/JPEG as ``input_image``, both inline as base64 data
URLs. Requests are not stored on OpenAI's side (``store=False``). The model's confidence values
are its own estimate, not a calibrated probability.
"""

import base64
import json
from collections.abc import Callable
from typing import Any

import openai

from invoice_intake.domain import (
    OUTPUT_SCHEMA,
    Document,
    ExtractionProviderError,
    RawExtraction,
)

INSTRUCTIONS = """\
You read one invoice and return its data in the required JSON format.
- Copy values as printed; never guess. Use null for anything the document does not show.
- Dates: YYYY-MM-DD. Currency: the ISO 4217 code (EUR, USD, GBP, ...), even if the invoice \
shows a symbol.
- Amounts and quantities: plain decimal strings with a dot and no thousands separators or \
currency symbols, for example "1234.50". Convert local formats such as "1.234,50 €".
- subtotal is before tax, tax is the tax amount, total is the amount due.
- line_items: one entry per invoice line, in order.
- confidence: for each field, your probability from 0 to 1 that the value is correct; use 0 \
for null fields. line_items gets one value for the whole table."""

CreateResponse = Callable[..., Any]


class OpenAIExtractionProvider:
    name = "openai"

    def __init__(self, *, model: str, create_response: CreateResponse) -> None:
        self._model = model
        self._create_response = create_response

    @classmethod
    def from_api_key(
        cls, *, api_key: str, model: str, timeout_seconds: float
    ) -> "OpenAIExtractionProvider":
        client = openai.OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=2)
        return cls(model=model, create_response=client.responses.create)

    def extract(self, document: Document) -> RawExtraction:
        try:
            response = self._create_response(
                model=self._model,
                instructions=INSTRUCTIONS,
                input=[
                    {
                        "role": "user",
                        "content": [
                            _document_part(document),
                            {"type": "input_text", "text": "Extract this invoice."},
                        ],
                    }
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "invoice_extraction",
                        "schema": OUTPUT_SCHEMA,
                        "strict": True,
                    }
                },
                store=False,
            )
        except openai.OpenAIError as error:
            raise ExtractionProviderError(
                f"OpenAI request failed: {type(error).__name__}: {error}"
            ) from error

        text = getattr(response, "output_text", "") or ""
        try:
            output: object = json.loads(text)
        except ValueError:
            output = text  # recorded as-is; validation will reject it
        return RawExtraction(self.name, self._model, output)


def _document_part(document: Document) -> dict[str, str]:
    data_url = f"data:{document.content_type};base64,{base64.b64encode(document.content).decode()}"
    if document.content_type == "application/pdf":
        return {"type": "input_file", "filename": "invoice.pdf", "file_data": data_url}
    return {"type": "input_image", "image_url": data_url, "detail": "high"}
