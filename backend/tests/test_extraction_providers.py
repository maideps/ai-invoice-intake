import base64
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest
from pydantic import SecretStr

from invoice_intake.domain import (
    FIELD_NAMES,
    OUTPUT_SCHEMA,
    Document,
    ExtractionProviderError,
    empty_output,
    parse_extraction,
)
from invoice_intake.infrastructure.extraction import (
    FakeExtractionProvider,
    OpenAIExtractionProvider,
    ProviderConfigurationError,
    make_extraction_provider,
)
from invoice_intake.worker import build_worker

from .helpers import IsolatedSettings

SAMPLES = Path(__file__).resolve().parents[2] / "samples" / "invoices"
PDF = Document("application/pdf", (SAMPLES / "invoice-001.pdf").read_bytes())
PNG = Document("image/png", b"\x89PNG\r\n\x1a\n" + b"\0" * 8)


# Fake provider ------------------------------------------------------------------------------


def test_fake_knows_every_committed_sample() -> None:
    assert FakeExtractionProvider(SAMPLES).known_documents == len(list(SAMPLES.glob("*.pdf")))


def test_fake_returns_the_ground_truth_with_confidence() -> None:
    truth = json.loads((SAMPLES / "invoice-001.json").read_text(encoding="utf-8"))

    raw = FakeExtractionProvider(SAMPLES).extract(PDF)

    assert (raw.provider, raw.model) == ("fake", "ground-truth")
    assert isinstance(raw.output, dict)
    assert raw.output["fields"] == truth["fields"]
    assert set(raw.output["confidence"]) == set(FIELD_NAMES)
    assert all(0.55 <= value <= 0.99 for value in raw.output["confidence"].values())


def test_fake_is_deterministic_and_does_not_share_state() -> None:
    first = FakeExtractionProvider(SAMPLES).extract(PDF).output
    second_provider = FakeExtractionProvider(SAMPLES)
    second = second_provider.extract(PDF).output
    assert first == second

    assert isinstance(second, dict)
    second["fields"]["vendor_name"] = "changed by a caller"
    assert second_provider.extract(PDF).output == first


def test_fake_gives_unknown_documents_empty_fields() -> None:
    raw = FakeExtractionProvider(SAMPLES).extract(PNG)

    assert raw.output == empty_output()
    assert parse_extraction(raw).fields.vendor_name is None


# Factory ------------------------------------------------------------------------------------


def test_factory_defaults_to_the_fake_provider() -> None:
    provider = make_extraction_provider(IsolatedSettings())

    assert isinstance(provider, FakeExtractionProvider)


def test_factory_builds_the_openai_provider_with_a_key() -> None:
    settings = IsolatedSettings(
        extraction_provider=" OpenAI ", openai_api_key=SecretStr("sk-test"), openai_model="m"
    )

    provider = make_extraction_provider(settings)

    assert isinstance(provider, OpenAIExtractionProvider)
    assert provider.name == "openai"


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"extraction_provider": "openai"}, "INVOICE_INTAKE_OPENAI_API_KEY must be set"),
        (
            {"extraction_provider": "openai", "openai_api_key": SecretStr("  ")},
            "INVOICE_INTAKE_OPENAI_API_KEY must be set",
        ),
        ({"extraction_provider": "claude"}, "unknown INVOICE_INTAKE_EXTRACTION_PROVIDER 'claude'"),
        ({"fake_samples_dir": Path("does/not/exist")}, "INVOICE_INTAKE_FAKE_SAMPLES_DIR"),
    ],
)
def test_bad_provider_settings_stop_the_worker_at_startup(
    settings: dict[str, Any], message: str
) -> None:
    with pytest.raises(ProviderConfigurationError, match=message):
        make_extraction_provider(IsolatedSettings(**settings))
    with pytest.raises(ProviderConfigurationError, match=message):
        build_worker(IsolatedSettings(**settings))


def test_provider_settings_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVOICE_INTAKE_EXTRACTION_PROVIDER", "openai")
    monkeypatch.setenv("INVOICE_INTAKE_OPENAI_API_KEY", "sk-from-env")
    monkeypatch.setenv("INVOICE_INTAKE_OPENAI_MODEL", "some-model")

    settings = IsolatedSettings()

    assert settings.extraction_provider == "openai"
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "sk-from-env"
    assert "sk-from-env" not in repr(settings)  # the key never shows up in logs or reprs


# OpenAI provider (no network: a stub stands in for client.responses.create) ---------------


class StubResponses:
    def __init__(self, reply: object) -> None:
        self.reply = reply
        self.requests: list[dict[str, Any]] = []

    def create(self, **request: Any) -> object:
        self.requests.append(request)
        if isinstance(self.reply, Exception):
            raise self.reply
        return SimpleNamespace(output_text=self.reply)


def _provider(reply: object) -> tuple[OpenAIExtractionProvider, StubResponses]:
    stub = StubResponses(reply)
    return OpenAIExtractionProvider(model="gpt-test", create_response=stub.create), stub


def test_openai_request_uses_strict_schema_and_attaches_the_pdf() -> None:
    provider, stub = _provider(json.dumps(empty_output()))

    provider.extract(PDF)

    (request,) = stub.requests
    assert request["model"] == "gpt-test"
    assert request["store"] is False
    assert request["text"]["format"] == {
        "type": "json_schema",
        "name": "invoice_extraction",
        "schema": OUTPUT_SCHEMA,
        "strict": True,
    }
    part = request["input"][0]["content"][0]
    assert part["type"] == "input_file"
    prefix = "data:application/pdf;base64,"
    assert part["file_data"].startswith(prefix)
    assert base64.b64decode(part["file_data"][len(prefix) :]) == PDF.content
    assert "never guess" in request["instructions"]


def test_openai_sends_images_as_input_image() -> None:
    provider, stub = _provider(json.dumps(empty_output()))

    provider.extract(PNG)

    part = stub.requests[0]["input"][0]["content"][0]
    assert part["type"] == "input_image"
    assert part["image_url"].startswith("data:image/png;base64,")


def test_openai_reply_is_parsed_as_json() -> None:
    provider, _ = _provider(json.dumps(empty_output()))

    raw = provider.extract(PDF)

    assert (raw.provider, raw.model, raw.output) == ("openai", "gpt-test", empty_output())


@pytest.mark.parametrize("reply", ["I cannot help with that.", "", None])
def test_openai_non_json_reply_is_kept_as_text(reply: str | None) -> None:
    provider, _ = _provider(reply)

    raw = provider.extract(PDF)

    assert raw.output == (reply or "")


@pytest.mark.parametrize(
    "error",
    [
        openai.APIConnectionError(request=httpx2.Request("POST", "https://api.openai.com")),
        openai.APITimeoutError(request=httpx2.Request("POST", "https://api.openai.com")),
        openai.RateLimitError(
            "slow down",
            response=httpx2.Response(429, request=httpx2.Request("POST", "https://x")),
            body=None,
        ),
    ],
    ids=["connection", "timeout", "rate-limit"],
)
def test_openai_failures_become_provider_errors(error: Exception) -> None:
    provider, _ = _provider(error)

    with pytest.raises(ExtractionProviderError, match=type(error).__name__):
        provider.extract(PDF)
