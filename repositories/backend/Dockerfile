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

# Dependencies first, exactly as locked and hash-checked (D-018), so a code change reuses
# this layer. Regenerate the lock with: npm run lock:backend
COPY requirements.lock ./
RUN pip install --require-hashes -r requirements.lock

COPY pyproject.toml ./
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
