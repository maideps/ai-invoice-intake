"""The one place that turns configuration into an extraction provider (D-005).

Called while the app starts, so a bad configuration stops startup with a clear message instead
of failing on the first invoice. Adding a provider means adding a class and an entry here.
"""

from invoice_intake.config import Settings
from invoice_intake.domain import ExtractionProvider

from .fake import FakeExtractionProvider
from .openai_provider import OpenAIExtractionProvider

PROVIDER_NAMES = ("fake", "openai")


class ProviderConfigurationError(RuntimeError):
    """The extraction provider settings are incomplete or invalid."""


def make_extraction_provider(settings: Settings) -> ExtractionProvider:
    name = settings.extraction_provider.strip().lower()
    if name == "fake":
        samples = settings.fake_samples_dir
        if not samples.is_dir():
            raise ProviderConfigurationError(
                f"the fake extraction provider needs the synthetic samples, but {samples} is "
                "not a directory; set INVOICE_INTAKE_FAKE_SAMPLES_DIR"
            )
        return FakeExtractionProvider(samples)
    if name == "openai":
        key = settings.openai_api_key.get_secret_value().strip() if settings.openai_api_key else ""
        if not key:
            raise ProviderConfigurationError(
                "INVOICE_INTAKE_OPENAI_API_KEY must be set when "
                "INVOICE_INTAKE_EXTRACTION_PROVIDER=openai"
            )
        return OpenAIExtractionProvider.from_api_key(
            api_key=key,
            model=settings.openai_model,
            timeout_seconds=settings.openai_timeout_seconds,
        )
    raise ProviderConfigurationError(
        f"unknown INVOICE_INTAKE_EXTRACTION_PROVIDER {settings.extraction_provider!r}; "
        f"expected one of: {', '.join(PROVIDER_NAMES)}"
    )
