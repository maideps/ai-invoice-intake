"""Upload the synthetic sample invoices into an empty instance (docker compose's ``seed`` service).

    python tools/seed_samples.py --api http://localhost:8000 --samples ../../samples/invoices

Does nothing when the API already holds invoices, so it is safe to run on every
``docker compose up``. The uploads go through the public API, like any other client: it signs
in first (by default as the demo reviewer, which ``python -m invoice_intake.accounts demo``
creates), and the worker extracts the invoices in the background.
"""

import argparse
import os
import sys
import time
from pathlib import Path

import httpx2 as httpx

# The demo reviewer (D-019); override with --username/--password or the environment.
DEFAULT_USERNAME = "sam.rivera"
DEFAULT_PASSWORD = "demo-reviewer"


def wait_for_api(client: httpx.Client, *, timeout_seconds: float) -> None:
    """Wait until ``GET /health`` answers, for a seed that starts alongside the API."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            if client.get("/health").status_code == 200:
                return
        except httpx.HTTPError:
            pass
        if time.monotonic() > deadline:
            raise TimeoutError(f"the API did not answer within {timeout_seconds:.0f} s")
        time.sleep(1)


def sign_in(client: httpx.Client, username: str, password: str) -> None:
    """Start a session; the client keeps its cookie for the uploads."""
    response = client.post("/auth/sign-in", json={"username": username, "password": password})
    if response.status_code == 401:
        raise PermissionError(f"could not sign in as {username!r}: wrong username or password")
    response.raise_for_status()


def seed(client: httpx.Client, samples_dir: Path) -> list[str]:
    """Upload every PDF in ``samples_dir`` unless invoices exist; return the uploaded names.

    The client must be signed in as someone allowed to upload."""
    existing = client.get("/invoices", params={"limit": 1}).raise_for_status().json()["total"]
    if existing:
        return []
    uploaded = []
    for pdf in sorted(samples_dir.glob("*.pdf")):
        client.post(
            "/invoices", files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")}
        ).raise_for_status()
        uploaded.append(pdf.name)
    return uploaded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--samples", type=Path, default=Path("samples/invoices"))
    parser.add_argument("--wait-seconds", type=float, default=60.0)
    parser.add_argument(
        "--username", default=os.environ.get("INVOICE_INTAKE_SEED_USERNAME", DEFAULT_USERNAME)
    )
    parser.add_argument(
        "--password", default=os.environ.get("INVOICE_INTAKE_SEED_PASSWORD", DEFAULT_PASSWORD)
    )
    args = parser.parse_args(argv)

    with httpx.Client(base_url=args.api, timeout=30.0) as client:
        wait_for_api(client, timeout_seconds=args.wait_seconds)
        sign_in(client, args.username, args.password)
        uploaded = seed(client, args.samples)
    if uploaded:
        print(f"Uploaded {len(uploaded)} sample invoices; the worker extracts them next.")
    else:
        print("Invoices already exist; nothing to seed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
