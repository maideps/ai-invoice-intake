"""A stand-in accounting system for the export webhook (docker compose's ``accounting`` service).

    python tools/demo_receiver.py --port 9000 --secret <INVOICE_INTAKE_EXPORT_WEBHOOK_SECRET>

``POST`` any path: checks ``X-Invoice-Intake-Signature`` when a secret is set (401 if it does
not match), records the delivery and logs one line. ``GET /deliveries`` lists what arrived,
newest last, with the parsed payload. Deliveries live in memory only.
"""

import argparse
import hashlib
import hmac
import json
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

SIGNATURE_HEADER = "X-Invoice-Intake-Signature"


@dataclass
class Receiver:
    secret: str | None = None
    deliveries: list[dict[str, Any]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def signature_ok(self, body: bytes, header: str | None) -> bool:
        if not self.secret:
            return True
        expected = "sha256=" + hmac.new(self.secret.encode(), body, hashlib.sha256).hexdigest()
        return header is not None and hmac.compare_digest(expected, header)

    def record(self, path: str, headers: dict[str, str], body: bytes) -> dict[str, Any]:
        delivery = {
            "received_at": datetime.now(timezone.utc).isoformat(),
            "path": path,
            "idempotency_key": headers.get("Idempotency-Key"),
            "delivery_id": headers.get("X-Invoice-Intake-Delivery"),
            "signed": SIGNATURE_HEADER in headers,
            "payload": json.loads(body),
        }
        with self.lock:
            self.deliveries.append(delivery)
        return delivery


def make_server(receiver: Receiver, host: str, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.rstrip("/") not in ("", "/deliveries"):
                self._answer(404, {"detail": "not found"})
                return
            with receiver.lock:
                self._answer(200, list(receiver.deliveries))

        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if not receiver.signature_ok(body, self.headers.get(SIGNATURE_HEADER)):
                print(f"rejected a delivery to {self.path}: bad signature", flush=True)
                self._answer(401, {"detail": "bad signature"})
                return
            try:
                delivery = receiver.record(self.path, dict(self.headers.items()), body)
            except ValueError:
                self._answer(400, {"detail": "the body is not JSON"})
                return
            payload = delivery["payload"]
            fields = payload.get("fields", {})
            print(
                f"booked {payload.get('filename')} ({fields.get('vendor_name')}, "
                f"{fields.get('currency')} {fields.get('total')}), approved by "
                f"{payload.get('approved_by')}; signature "
                f"{'ok' if receiver.secret else 'not checked'}",
                flush=True,
            )
            self._answer(200, {"status": "booked"})

        def _answer(self, status: int, body: object) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: Any) -> None:
            pass  # one line per delivery is printed above; skip the access log

    return ThreadingHTTPServer((host, port), Handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--secret", default=None, help="shared HMAC secret; unset: no check")
    args = parser.parse_args(argv)

    server = make_server(Receiver(secret=args.secret or None), args.host, args.port)
    check = "checking signatures" if args.secret else "not checking signatures"
    print(f"Demo accounting system listening on port {args.port} ({check})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
