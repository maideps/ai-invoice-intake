"""The Redis extraction queue against a real Redis (D-010)."""

from uuid import uuid4

import pytest
import redis

from invoice_intake.infrastructure.queue import Job, RedisExtractionQueue

pytestmark = pytest.mark.redis


class FakeTime:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def _queue(
    client: redis.Redis, clock: FakeTime | None = None, worker: str = "w1"
) -> RedisExtractionQueue:
    return RedisExtractionQueue(client, worker_id=worker, clock=clock or FakeTime())


def test_jobs_come_out_first_in_first_out(redis_client: redis.Redis) -> None:
    queue = _queue(redis_client)
    ids = [uuid4() for _ in range(3)]
    for invoice_id in ids:
        queue.enqueue(invoice_id)

    reserved = [queue.reserve(timeout_seconds=1) for _ in ids]

    assert [job.invoice_id for job in reserved if job] == ids
    assert all(job and job.attempt == 1 for job in reserved)


def test_a_reserved_job_is_held_until_acknowledged(redis_client: redis.Redis) -> None:
    queue = _queue(redis_client)
    queue.enqueue(uuid4())

    job = queue.reserve(timeout_seconds=1)
    assert job is not None
    assert queue.sizes() == {"ready": 0, "delayed": 0, "processing": 1}

    queue.ack(job)
    assert queue.sizes() == {"ready": 0, "delayed": 0, "processing": 0}


def test_an_empty_queue_times_out_with_nothing(redis_client: redis.Redis) -> None:
    assert _queue(redis_client).reserve(timeout_seconds=0.1) is None


def test_a_delayed_retry_waits_for_its_time(redis_client: redis.Redis) -> None:
    clock = FakeTime()
    queue = _queue(redis_client, clock)
    retry = Job(uuid4(), attempt=2)

    queue.schedule(retry, delay_seconds=10)

    assert queue.reserve(timeout_seconds=0.1) is None
    clock.now += 9.9
    assert queue.reserve(timeout_seconds=0.1) is None
    clock.now += 0.2
    assert queue.reserve(timeout_seconds=0.1) == retry
    assert queue.sizes()["delayed"] == 0


def test_jobs_held_by_a_crashed_worker_come_back_on_restart(redis_client: redis.Redis) -> None:
    before_crash = _queue(redis_client, worker="w1")
    first, second = uuid4(), uuid4()
    before_crash.enqueue(first)
    before_crash.enqueue(second)
    held = before_crash.reserve(timeout_seconds=1)  # then the worker dies without ack
    assert held is not None and held.invoice_id == first

    restarted = _queue(redis_client, worker="w1")
    assert restarted.recover() == 1

    # The recovered job is first in line again.
    assert restarted.reserve(timeout_seconds=1) == held
    assert restarted.reserve(timeout_seconds=1) == Job(second)


def test_workers_with_different_ids_do_not_steal_each_others_jobs(
    redis_client: redis.Redis,
) -> None:
    one, two = _queue(redis_client, worker="w1"), _queue(redis_client, worker="w2")
    one.enqueue(uuid4())
    held = one.reserve(timeout_seconds=1)

    assert two.recover() == 0
    assert held is not None and one.sizes()["processing"] == 1


def test_job_encoding_round_trips() -> None:
    job = Job(uuid4(), attempt=3)

    assert Job.decode(job.encode()) == job


def test_from_url_does_not_connect_until_used() -> None:
    queue = RedisExtractionQueue.from_url("redis://127.0.0.1:1/0")  # nothing listens there

    with pytest.raises(redis.ConnectionError):
        queue.enqueue(uuid4())
