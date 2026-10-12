from pathlib import Path

import pytest
from check_domain_imports import DEFAULT_ROOT, find_violations, main


def test_real_domain_layer_follows_the_rule() -> None:
    assert find_violations(DEFAULT_ROOT) == []


def test_main_reports_pass(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check_domain_imports.py"]) == 0
    assert capsys.readouterr().out.startswith("PASS:")


def test_planted_bad_imports_are_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "good.py").write_text(
        "from __future__ import annotations\n"
        "import json\n"
        "from decimal import Decimal\n"
        "from . import status\n"
        "from .errors import DomainError\n"
        "from invoice_intake.domain.status import InvoiceStatus\n",
        encoding="utf-8",
    )
    (tmp_path / "bad.py").write_text(
        "import fastapi\n"
        "from invoice_intake.infrastructure import db\n"
        "from .. import config\n"
        "import os, pydantic\n",
        encoding="utf-8",
    )
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.py").write_text(
        "from .. import status\nfrom ... import api\n", encoding="utf-8"
    )

    assert find_violations(tmp_path) == [
        "bad.py:1: fastapi",
        "bad.py:2: invoice_intake.infrastructure",
        "bad.py:3: ..",
        "bad.py:4: pydantic",
        "sub/nested.py:2: ...",
    ]

    assert main(["check_domain_imports.py", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "PASS" not in out
    assert "bad.py:1: fastapi" in out
