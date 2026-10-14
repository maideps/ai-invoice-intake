from collections.abc import Iterator

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from invoice_intake.domain import ActorKind, Document, InvoiceStatus, parse_field_patch
from invoice_intake.infrastructure.database import make_engine, make_session_factory
from invoice_intake.infrastructure.repository import SqlInvoiceRepository
from invoice_intake.infrastructure.tables import Base

from .conftest import alembic_config
from .domain_helpers import ACTORS, at, invoice_in

pytestmark = pytest.mark.postgres

TABLES = {
    "invoices",
    "invoice_line_items",
    "audit_events",
    "invoice_documents",
    "accounts",
    "sessions",
}


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


def test_downgrade_below_0002_refuses_to_drop_extraction_events(clean_database_url: str) -> None:
    config = alembic_config(clean_database_url)
    command.upgrade(config, "head")
    invoice = invoice_in(InvoiceStatus.EXTRACTING)
    invoice.record_rejected_extraction(provider="p", model="m", output="x", errors=["e"], at=at(9))
    engine = make_engine(clean_database_url)
    try:
        with make_session_factory(engine).begin() as session:
            SqlInvoiceRepository(session).add(invoice, Document("application/pdf", b"%PDF-1"))
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="1 extraction audit event"):
        command.downgrade(config, "0001")

    assert _columns(clean_database_url, "audit_events") >= {"details"}  # still at 0002


def _columns(url: str, table: str) -> set[str]:
    engine = create_engine(url)
    try:
        return {column["name"] for column in inspect(engine).get_columns(table)}
    finally:
        engine.dispose()


def test_downgrade_below_0003_refuses_to_drop_reviewer_edits(clean_database_url: str) -> None:
    config = alembic_config(clean_database_url)
    command.upgrade(config, "head")
    invoice = invoice_in(InvoiceStatus.NEEDS_REVIEW)
    invoice.edit_fields(
        parse_field_patch(invoice.fields, {"total": "1.00"}),
        actor=ACTORS[ActorKind.USER],
        at=at(9),
    )
    engine = make_engine(clean_database_url)
    try:
        with make_session_factory(engine).begin() as session:
            SqlInvoiceRepository(session).add(invoice, Document("application/pdf", b"%PDF-1"))
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="1 fields_edited audit event"):
        command.downgrade(config, "0002")


def test_downgrade_below_0004_refuses_to_drop_failed_invoices(clean_database_url: str) -> None:
    config = alembic_config(clean_database_url)
    command.upgrade(config, "head")
    engine = make_engine(clean_database_url)
    try:
        with make_session_factory(engine).begin() as session:
            SqlInvoiceRepository(session).add(
                invoice_in(InvoiceStatus.FAILED), Document("application/pdf", b"%PDF-1")
            )
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="failed invoice row"):
        command.downgrade(config, "0003")


def test_downgrade_below_0005_refuses_to_drop_export_failures(clean_database_url: str) -> None:
    config = alembic_config(clean_database_url)
    command.upgrade(config, "head")
    invoice = invoice_in(InvoiceStatus.APPROVED)
    invoice.record_export_failure(
        attempt=1, error="HTTP 500", final=False, status_code=500, at=at(9)
    )
    engine = make_engine(clean_database_url)
    try:
        with make_session_factory(engine).begin() as session:
            SqlInvoiceRepository(session).add(invoice, Document("application/pdf", b"%PDF-1"))
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="1 export_failed audit event"):
        command.downgrade(config, "0004")
