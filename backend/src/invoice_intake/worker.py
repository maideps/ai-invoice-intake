"""The background worker: a second composition root, run as ``python -m invoice_intake.worker``.

It takes jobs from the Redis queue: extraction of uploads (D-010) and export of approved invoices
to the webhook (feat-010). Each job is one attempt; retries are scheduled with exponential
backoff, and every so often it re-queues work whose job was lost. Ctrl+C or SIGTERM stops it
after the current job.
"""

import logging
import signal
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from types import FrameType

from sqlalchemy import Engine

from invoice_intake.config import Settings, get_settings
from invoice_intake.domain import ExtractionProvider
from invoice_intake.infrastructure.database import make_engine, make_session_factory
from invoice_intake.infrastructure.export_webhook import HttpWebhookSender
from invoice_intake.infrastructure.extraction import make_extraction_provider
from invoice_intake.infrastructure.queue import Job, RedisExtractionQueue
from invoice_intake.infrastructure.repository import SqlInvoiceRepository
from invoice_intake.services.export import ExportRunner, ExportService
from invoice_intake.services.extraction import (
    AttemptOutcome,
    AttemptResult,
    ExtractionRunner,
    ExtractionService,
)

log = logging.getLogger("invoice_intake.worker")

# How long an invoice may sit in "uploaded" before the sweep assumes its job was lost.
STALE_UPLOAD_GRACE = timedelta(seconds=30)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def backoff_seconds(base: float, attempt: int) -> float:
    """Delay before the attempt after ``attempt``: base, 2x base, 4x base, ..."""
    return base * 2.0 ** (attempt - 1)


@dataclass
class Worker:
    queue: RedisExtractionQueue
    runner: ExtractionRunner
    sweep: Callable[[], int]
    retry_base_seconds: float
    sweep_every_seconds: float
    # None when no export webhook is configured: export jobs are dropped and invoices stay
    # approved; the sweep queues them again once a webhook is set.
    export_runner: ExportRunner | None = None
    export_retry_base_seconds: float = 10.0
    engine: Engine | None = None
    closers: list[Callable[[], None]] = field(default_factory=list)
    monotonic: Callable[[], float] = field(default=time.monotonic)

    def handle(self, job: Job) -> AttemptOutcome:
        """Run one attempt; reschedule it if it should be retried; always release the job."""
        exporting = job.kind == "export"
        base = self.export_retry_base_seconds if exporting else self.retry_base_seconds
        try:
            if exporting and self.export_runner is None:
                outcome = AttemptOutcome(AttemptResult.SKIPPED, "export webhook not configured")
            elif exporting:
                assert self.export_runner is not None
                outcome = self.export_runner.run(job.invoice_id, job.attempt)
            else:
                outcome = self.runner.run(job.invoice_id, job.attempt)
        except Exception as error:  # database or other unexpected trouble: same attempt, later
            log.exception(
                "invoice %s: %s attempt %d crashed", job.invoice_id, job.kind, job.attempt
            )
            self.queue.schedule(job, delay_seconds=backoff_seconds(base, 1))
            self.queue.ack(job)
            return AttemptOutcome(AttemptResult.RETRY, f"crashed: {error}")
        if outcome.result is AttemptResult.RETRY:
            delay = backoff_seconds(base, job.attempt)
            next_job = Job(job.invoice_id, job.attempt + 1, job.kind)
            self.queue.schedule(next_job, delay_seconds=delay)
        self.queue.ack(job)
        log.info(
            "invoice %s: %s attempt %d %s %s",
            job.invoice_id,
            job.kind,
            job.attempt,
            outcome.result.value,
            outcome.detail,
        )
        return outcome

    def run(self, stop: threading.Event, *, poll_seconds: float = 1.0) -> None:
        recovered = self.queue.recover()
        if recovered:
            log.info("recovered %d job(s) left over from a previous run", recovered)
        self._sweep()
        last_sweep = self.monotonic()
        while not stop.is_set():
            job = self.queue.reserve(timeout_seconds=poll_seconds)
            if job is not None:
                self.handle(job)
            if self.monotonic() - last_sweep >= self.sweep_every_seconds:
                self._sweep()
                last_sweep = self.monotonic()

    def close(self) -> None:
        for close in self.closers:
            close()
        if self.engine is not None:
            self.engine.dispose()

    def _sweep(self) -> None:
        try:
            queued = self.sweep()
        except Exception:
            log.exception("sweep for stuck uploads failed")
            return
        if queued:
            log.info("re-queued %d upload(s) that were waiting without a job", queued)


def build_worker(
    settings: Settings,
    *,
    provider: ExtractionProvider | None = None,
    queue: RedisExtractionQueue | None = None,
    stale_upload_grace: timedelta = STALE_UPLOAD_GRACE,
) -> Worker:
    """Wire the worker. Bad provider settings raise ``ProviderConfigurationError`` here, at
    startup, rather than on the first job."""
    resolved_provider = provider or make_extraction_provider(settings)
    resolved_queue = queue or RedisExtractionQueue.from_url(
        settings.redis_url, worker_id=settings.worker_id
    )
    engine = make_engine(settings.database_url)
    sessions = make_session_factory(engine)

    @contextmanager
    def services() -> Iterator[ExtractionService]:
        with sessions.begin() as session:
            yield ExtractionService(SqlInvoiceRepository(session), resolved_queue, clock=utc_now)

    @contextmanager
    def export_services() -> Iterator[ExportService]:
        with sessions.begin() as session:
            yield ExportService(SqlInvoiceRepository(session), resolved_queue, clock=utc_now)

    sender = None
    if settings.export_webhook_url:
        secret = settings.export_webhook_secret
        sender = HttpWebhookSender(
            settings.export_webhook_url,
            secret=secret.get_secret_value() if secret else None,
            timeout_seconds=settings.export_timeout_seconds,
        )

    def sweep() -> int:
        cutoff = utc_now() - stale_upload_grace
        with services() as service:
            queued = service.requeue_stale_uploads(older_than=cutoff)
        if sender is not None:
            with export_services() as exports:
                queued += exports.requeue_unsent(approved_before=cutoff)
        return queued

    return Worker(
        queue=resolved_queue,
        runner=ExtractionRunner(
            services, resolved_provider, max_attempts=settings.extraction_max_attempts
        ),
        sweep=sweep,
        retry_base_seconds=settings.extraction_retry_base_seconds,
        sweep_every_seconds=settings.worker_sweep_seconds,
        export_runner=(
            ExportRunner(export_services, sender, max_attempts=settings.export_max_attempts)
            if sender is not None
            else None
        ),
        export_retry_base_seconds=settings.export_retry_base_seconds,
        engine=engine,
        closers=[sender.close] if sender is not None else [],
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    logging.getLogger().setLevel(settings.log_level)
    worker = build_worker(settings)
    stop = threading.Event()

    def request_stop(signum: int, _: FrameType | None) -> None:
        log.info("stopping after the current job (signal %d)", signum)
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    log.info(
        "worker started (id %s): provider %s, up to %d attempts per invoice; export %s",
        settings.worker_id,
        settings.extraction_provider,
        settings.extraction_max_attempts,
        "on" if settings.export_webhook_url else "off (no INVOICE_INTAKE_EXPORT_WEBHOOK_URL)",
    )
    try:
        worker.run(stop)
    finally:
        worker.close()
        log.info("worker stopped")


if __name__ == "__main__":
    main()
