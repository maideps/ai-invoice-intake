from collections.abc import Iterator

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from invoice_intake.infrastructure.tables import Base

from .conftest import alembic_config

pytestmark = pytest.mark.postgres

TABLES = {"invoices", "invoice_line_items", "audit_events", "invoice_documents"}


@pytest.fixture
def clean_database_url(postgres_url: str) -> Iterator[str]:
    """A brand-new, empty database in the session's container."""
    admin = create_engine(postgres_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text("DROP DATABASE IF EXISTS migrations_check"))
        connection.execute(text("CREATE DATABASE migrations_check"))
    yield (
        make_url(postgres_url)
        .set(database="migrations_check")
        .render_as_string(hide_password=False)
    )
    with admin.connect() as connection:
        connection.execute(text("DROP DATABASE migrations_check WITH (FORCE)"))
    admin.dispose()


def _tables(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names()) - {"alembic_version"}
    finally:
        engine.dispose()


def test_migrations_apply_to_a_clean_database_and_reverse(clean_database_url: str) -> None:
    config = alembic_config(clean_database_url)
    assert _tables(clean_database_url) == set()

    command.upgrade(config, "head")
    assert _tables(clean_database_url) == TABLES

    command.downgrade(config, "base")
    assert _tables(clean_database_url) == set()

    command.upgrade(config, "head")
    assert _tables(clean_database_url) == TABLES


def test_models_match_the_migrated_schema(migrated_url: str) -> None:
    engine = create_engine(migrated_url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            differences = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    assert differences == []
