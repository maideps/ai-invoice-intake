from pathlib import Path

import pytest
from check_layer_imports import LAYERS, find_violations, main


def _write(root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


@pytest.fixture
def package(tmp_path: Path) -> Path:
    """A throwaway ``invoice_intake`` package with one good and one bad module per layer."""
    root = tmp_path / "invoice_intake"
    _write(
        root,
        "domain/good.py",
        "from __future__ import annotations\n"
        "import json\n"
        "from decimal import Decimal\n"
        "from . import status\n"
        "from .errors import DomainError\n"
        "from invoice_intake.domain.status import InvoiceStatus\n",
    )
    _write(
        root,
        "domain/bad.py",
        "import fastapi\n"
        "from invoice_intake.infrastructure import db\n"
        "from .. import config\n"
        "import os, pydantic\n",
    )
    _write(root, "domain/sub/nested.py", "from .. import status\nfrom ... import api\n")
    _write(
        root,
        "api/good.py",
        "from fastapi import APIRouter\n"
        "from invoice_intake.domain import Invoice\n"
        "from invoice_intake.services.intake import IntakeService\n"
        "from .schemas import InvoiceOut\n",
    )
    _write(
        root,
        "api/bad.py",
        "import invoice_intake.infrastructure.tables\n"
        "from invoice_intake import infrastructure\n"
        "from ..infrastructure.repository import SqlInvoiceRepository\n"
        "from invoice_intake.main import create_app\n",
    )
    _write(root, "services/bad.py", "from invoice_intake.api.schemas import InvoiceOut\n")
    return root


def test_real_package_follows_every_rule() -> None:
    for layer in LAYERS:
        assert find_violations(layer) == [], layer


def test_domain_rule(package: Path) -> None:
    assert find_violations("domain", package) == [
        "domain/bad.py:1: fastapi",
        "domain/bad.py:2: invoice_intake.infrastructure.db",
        "domain/bad.py:3: invoice_intake.config",
        "domain/bad.py:4: pydantic",
        "domain/sub/nested.py:2: invoice_intake.api",
    ]


def test_api_rule_catches_every_import_form(package: Path) -> None:
    assert find_violations("api", package) == [
        "api/bad.py:1: invoice_intake.infrastructure.tables",
        "api/bad.py:2: invoice_intake.infrastructure",
        "api/bad.py:3: invoice_intake.infrastructure.repository.SqlInvoiceRepository",
        "api/bad.py:4: invoice_intake.main.create_app",
    ]


def test_services_must_not_import_api(package: Path) -> None:
    assert find_violations("services", package) == [
        "services/bad.py:1: invoice_intake.api.schemas.InvoiceOut"
    ]


def test_main_reports_pass_and_fail(package: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", "domain", "api", "services"]) == 0
    assert capsys.readouterr().out.startswith("PASS: layer imports follow the rules for domain")

    assert main(["check", "api"], package) == 1
    out = capsys.readouterr().out
    assert "PASS" not in out
    assert "api/bad.py:2: invoice_intake.infrastructure" in out


@pytest.mark.parametrize("argv", [["check"], ["check", "frontend"]])
def test_main_rejects_unknown_layers(argv: list[str]) -> None:
    assert main(argv) == 2
