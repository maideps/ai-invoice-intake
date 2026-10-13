"""Write the API's OpenAPI document for the frontend's generated types.

From the repository root: ``npm run api:types`` (this script, then ``openapi-typescript``).
A backend test fails when the committed ``frontend/src/api/openapi.json`` is out of date.
"""

import json
import sys
from pathlib import Path

from invoice_intake.config import Settings
from invoice_intake.main import create_app

TARGET = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "openapi.json"


def openapi_document() -> str:
    """The OpenAPI JSON, independent of local environment settings."""
    settings = Settings(_env_file=None, app_name="AI Invoice Intake")  # type: ignore[call-arg]
    schema = create_app(settings).openapi()
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(openapi_document(), encoding="utf-8", newline="\n")
    print(f"Wrote {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
