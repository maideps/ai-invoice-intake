"""Shared fixtures. PostgreSQL fixtures start one throwaway container per test session.

Tests that use them need Docker. Without it they fail (not skip) with a message saying so:
a green test run must mean the persistence code ran against a real PostgreSQL.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
import redis
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from invoice_intake.infrastructure.database import make_engine, make_session_factory

from .webhook_server import webhook  # noqa: F401  (a fixture: a local export webhook)

BACKEND = Path(__file__).resolve().parents[1]
POSTGRES_IMAGE = "postgres:16-alpine"
TABLES = "invoices, invoice_line_items, audit_events, invoice_documents, accounts, sessions"


def alembic_config(url: str) -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))  # configparser escaping
    config.attributes["configure_logger"] = False  # leave pytest's logging alone
    return config


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """Connection URL of a fresh PostgreSQL container for this test session."""
    from testcontainers.community.postgres import PostgresContainer

    try:  # creating the container object already talks to Docker
        container = PostgresContainer(POSTGRES_IMAGE, driver="psycopg")
        container.start()
    except Exception as error:  # docker missing, not running, or image pull failed
        pytest.fail(
            "PostgreSQL integration tests need Docker running: testcontainers could not start "
            f"{POSTGRES_IMAGE} ({type(error).__name__}: {error}). Start Docker Desktop and rerun, "
            'or run only the other tests with: pytest -m "not postgres"',
            pytrace=False,
        )
    try:
        yield container.get_connection_url()
    finally:
        container.stop()


@pytest.fixture(scope="session")
def migrated_url(postgres_url: str) -> str:
    command.upgrade(alembic_config(postgres_url), "head")
    return postgres_url


@pytest.fixture
def engine(migrated_url: str) -> Iterator[Engine]:
    """The migrated database, emptied after each test.

    TRUNCATE is a statement-level operation, so the row-level append-only trigger on
    audit_events does not block cleanup.
    """
    engine = make_engine(migrated_url)
    try:
        yield engine
    finally:
        with engine.begin() as connection:
            connection.execute(text(f"TRUNCATE {TABLES}"))
        engine.dispose()


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    return make_session_factory(engine)


REDIS_IMAGE = "redis:7-alpine"


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    """URL of a fresh Redis container for this test session (same Docker rule as PostgreSQL)."""
    from testcontainers.community.redis import RedisContainer

    try:
        container = RedisContainer(REDIS_IMAGE)
        container.start()
    except Exception as error:
        pytest.fail(
            "Redis queue tests need Docker running: testcontainers could not start "
            f"{REDIS_IMAGE} ({type(error).__name__}: {error}). Start Docker Desktop and rerun, "
            'or run only the other tests with: pytest -m "not postgres and not redis"',
            pytrace=False,
        )
    try:
        host = container.get_container_host_ip()
        yield f"redis://{host}:{container.get_exposed_port(6379)}/0"
    finally:
        container.stop()


@pytest.fixture
def redis_client(redis_url: str) -> Iterator[redis.Redis]:
    """A client on an emptied database; emptied again afterwards."""
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    client.flushdb()
    try:
        yield client
    finally:
        client.flushdb()
        client.close()
