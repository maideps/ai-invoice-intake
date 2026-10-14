# One image for the API, the worker, the migrations and the compose helper tools (D-015).
#
#   docker compose build                     (from the repository root; the usual way)
#   docker build --build-context samples=samples -t invoice-intake-backend repositories/backend
#
# The synthetic samples come from a second build context, so the fake extraction provider
# recognises them inside the container while the build context stays repositories/backend/.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, from pyproject.toml alone, so a code change reuses this layer.
COPY pyproject.toml ./
COPY src/invoice_intake/__init__.py src/invoice_intake/__init__.py
RUN pip install . && pip uninstall --yes invoice-intake

COPY src ./src
RUN pip install --no-deps . && rm -rf build src/*.egg-info

COPY alembic.ini ./
COPY migrations ./migrations
COPY tools/seed_samples.py tools/demo_receiver.py ./tools/
COPY --from=samples invoices ./samples/invoices

ENV INVOICE_INTAKE_FAKE_SAMPLES_DIR=/app/samples/invoices

RUN useradd --system --uid 10001 --no-create-home app
USER app

EXPOSE 8000
CMD ["uvicorn", "invoice_intake.main:app", "--host", "0.0.0.0", "--port", "8000"]
