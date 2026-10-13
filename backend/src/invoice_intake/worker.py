"""The extraction worker: a second composition root, run as ``python -m invoice_intake.worker``.

It takes jobs from the Redis queue, runs one extraction attempt per job, schedules retries with
exponential backoff, and every so often re-queues uploads whose job was lost. Ctrl+C or SIGTERM
stops it after the current job.
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
from invoice_intake.infrastructure.extraction import make_extraction_provider
from invoice_intake.infrastructure.queue import Job, RedisExtractionQueue
from invoice_intake.infrastructure.repository import SqlInvoiceRepository
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
    engine: Engine | None = None
    monotonic: Callable[[], float] = field(default=time.monotonic)

    def handle(self, job: Job) -> AttemptOutcome:
        """Run one attempt; reschedule it if it should be retried; always release the job."""
        try:
            outcome = self.runner.run(job.invoice_id, job.attempt)
        except Exception as error:  # database or other unexpected trouble: same attempt, later
            log.exception("invoice %s: attempt %d crashed", job.invoice_id, job.attempt)
            self.queue.schedule(job, delay_seconds=backoff_seconds(self.retry_base_seconds, 1))
            self.queue.ack(job)
            return AttemptOutcome(AttemptResult.RETRY, f"crashed: {error}")
        if outcome.result is AttemptResult.RETRY:
            delay = backoff_seconds(self.retry_base_seconds, job.attempt)
            self.queue.schedule(Job(job.invoice_id, job.attempt + 1), delay_seconds=delay)
        self.queue.ack(job)
        log.info(
            "invoice %s: attempt %d %s %s",
            job.invoice_id,
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

    def sweep() -> int:
        with services() as service:
            return service.requeue_stale_uploads(older_than=utc_now() - stale_upload_grace)

    return Worker(
        queue=resolved_queue,
        runner=ExtractionRunner(
            services, resolved_provider, max_attempts=settings.extraction_max_attempts
        ),
        sweep=sweep,
        retry_base_seconds=settings.extraction_retry_base_seconds,
        sweep_every_seconds=settings.worker_sweep_seconds,
        engine=engine,
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
        "worker started (id %s): provider %s, up to %d attempts per invoice",
        settings.worker_id,
        settings.extraction_provider,
        settings.extraction_max_attempts,
    )
    try:
        worker.run(stop)
    finally:
        worker.close()
        log.info("worker stopped")


if __name__ == "__main__":
    main()
