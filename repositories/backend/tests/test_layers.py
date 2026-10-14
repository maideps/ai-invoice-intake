import importlib

import pytest


@pytest.mark.parametrize("layer", ["api", "services", "domain", "infrastructure"])
def test_layer_packages_exist(layer: str) -> None:
    assert importlib.import_module(f"invoice_intake.{layer}").__doc__
