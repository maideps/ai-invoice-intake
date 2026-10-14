"""Deliver approved invoices to the export webhook over HTTP (implements ``ExportSender``).

Each delivery is a JSON POST with:

- ``Idempotency-Key``: the invoice id, the same on every attempt, for de-duplication;
- ``X-Invoice-Intake-Delivery``: unique per attempt, for the receiver's logs;
- ``X-Invoice-Intake-Signature: sha256=<hex>``: HMAC-SHA256 of the exact body with the shared
  secret, when one is configured, so the receiver can check the sender.

Any 2xx is success; anything else (other statuses, timeouts, connection errors) is a failed
attempt with a short, readable reason.
"""

import hashlib
import hmac
import json
import uuid
from typing import Any

import httpx2 as httpx

from invoice_intake.services.export import ExportDeliveryError

MAX_BODY_IN_ERROR = 200


def signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class HttpWebhookSender:
    def __init__(
        self,
        url: str,
        *,
        secret: str | None = None,
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._url = url
        self._secret = secret
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def send(self, payload: dict[str, Any], *, idempotency_key: str) -> None:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "invoice-intake-export/1",
            "Idempotency-Key": idempotency_key,
            "X-Invoice-Intake-Delivery": str(uuid.uuid4()),
        }
        if self._secret:
            headers["X-Invoice-Intake-Signature"] = signature(self._secret, body)
        try:
            response = self._client.post(self._url, content=body, headers=headers)
        except httpx.TimeoutException as error:
            raise ExportDeliveryError(f"the webhook did not answer in time ({error})") from error
        except httpx.HTTPError as error:
            raise ExportDeliveryError(f"could not reach the webhook: {error}") from error
        if not 200 <= response.status_code < 300:
            text = response.text.strip().replace("\n", " ")[:MAX_BODY_IN_ERROR]
            raise ExportDeliveryError(
                f"HTTP {response.status_code}" + (f": {text}" if text else ""),
                status_code=response.status_code,
            )

    def close(self) -> None:
        self._client.close()
