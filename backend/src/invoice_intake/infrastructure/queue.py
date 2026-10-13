"""A small reliable job queue on Redis for extraction work (D-010).

Keys (under ``<namespace>:extraction:``):

- ``ready``: list of jobs waiting, oldest at the right end.
- ``delayed``: sorted set of retries, scored by the time they become ready.
- ``processing:<worker id>``: the job a worker is handling. ``reserve`` moves a job here
  atomically (``BLMOVE``); ``ack`` removes it when done. If the worker dies, ``recover`` on its
  next start puts the job back, so a crash never loses work.

Delivery is at least once, so a job may run twice; the extraction steps are idempotent.
"""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

import redis

# Moves due retries from the delayed set to the ready list in one atomic step.
_PROMOTE_DUE = """
local due = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, 100)
for _, job in ipairs(due) do
    redis.call('ZREM', KEYS[1], job)
    redis.call('LPUSH', KEYS[2], job)
end
return #due
"""


@dataclass(frozen=True)
class Job:
    invoice_id: UUID
    attempt: int = 1

    def encode(self) -> str:
        return json.dumps({"attempt": self.attempt, "invoice_id": str(self.invoice_id)})

    @classmethod
    def decode(cls, raw: str) -> "Job":
        data = json.loads(raw)
        return cls(invoice_id=UUID(data["invoice_id"]), attempt=int(data["attempt"]))


class RedisExtractionQueue:
    def __init__(
        self,
        client: redis.Redis,  # created with decode_responses=True
        *,
        worker_id: str = "worker",
        namespace: str = "invoice-intake",
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._client = client
        self._clock = clock
        base = f"{namespace}:extraction"
        self.ready_key = f"{base}:ready"
        self.delayed_key = f"{base}:delayed"
        self.processing_key = f"{base}:processing:{worker_id}"
        self._promote = client.register_script(_PROMOTE_DUE)

    @classmethod
    def from_url(cls, url: str, **options: Any) -> "RedisExtractionQueue":
        """Connects lazily: nothing talks to Redis until the first command."""
        return cls(redis.Redis.from_url(url, decode_responses=True), **options)

    def enqueue(self, invoice_id: UUID) -> None:
        self.schedule(Job(invoice_id))

    def schedule(self, job: Job, *, delay_seconds: float = 0) -> None:
        if delay_seconds <= 0:
            self._client.lpush(self.ready_key, job.encode())
        else:
            self._client.zadd(self.delayed_key, {job.encode(): self._clock() + delay_seconds})

    def reserve(self, *, timeout_seconds: float) -> Job | None:
        """The next ready job (waiting up to ``timeout_seconds``), now held by this worker."""
        self._promote(keys=[self.delayed_key, self.ready_key], args=[self._clock()])
        raw = self._client.blmove(
            self.ready_key,
            self.processing_key,
            timeout_seconds,  # type: ignore[arg-type]  # Redis accepts fractional timeouts
            "RIGHT",
            "LEFT",
        )
        return None if raw is None else Job.decode(cast(str, raw))

    def ack(self, job: Job) -> None:
        """The job is finished (done, rescheduled or dropped): stop holding it."""
        self._client.lrem(self.processing_key, 1, job.encode())

    def recover(self) -> int:
        """Return jobs this worker held when it stopped to the front of the queue."""
        moved = 0
        while self._client.lmove(self.processing_key, self.ready_key, "LEFT", "RIGHT"):
            moved += 1
        return moved

    def sizes(self) -> dict[str, int]:
        return {
            "ready": self._client.llen(self.ready_key),
            "delayed": self._client.zcard(self.delayed_key),
            "processing": self._client.llen(self.processing_key),
        }
