"""A real local HTTP server standing in for the accounting system's export webhook."""

import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


@dataclass
class Delivery:
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass
class Webhook:
    """Records deliveries; answers with ``statuses`` in turn (then 200), after ``delay`` seconds."""

    url: str
    deliveries: list[Delivery] = field(default_factory=list)
    statuses: list[int] = field(default_factory=list)
    delay: float = 0.0


@pytest.fixture
def webhook() -> Iterator[Webhook]:
    state = Webhook(url="")

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            state.deliveries.append(Delivery(self.path, dict(self.headers.items()), body))
            if state.delay:
                time.sleep(state.delay)
            status = state.statuses.pop(0) if state.statuses else 200
            text = b"ok" if status < 300 else b"temporarily unavailable"
            self.send_response(status)
            self.send_header("Content-Length", str(len(text)))
            self.end_headers()
            self.wfile.write(text)

        def log_message(self, *_: object) -> None:  # keep test output quiet
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state.url = f"http://127.0.0.1:{server.server_address[1]}/hooks/invoices"
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
