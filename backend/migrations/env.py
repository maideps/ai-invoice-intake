"""Alembic environment: runs migrations online against the configured PostgreSQL."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from invoice_intake.config import Settings
from invoice_intake.infrastructure.tables import Base

target_metadata = Base.metadata

# Command-line runs log "Running upgrade ..." lines; tests (no config file) stay quiet.
if context.config.config_file_name is not None and context.config.attributes.get(
    "configure_logger", True
):
    fileConfig(context.config.config_file_name, disable_existing_loggers=False)


def _database_url() -> str:
    # Tests set the URL on the Alembic config; everyone else uses the application settings.
    configured = context.config.get_main_option("sqlalchemy.url")
    return configured or Settings().database_url


def run_migrations() -> None:
    engine = create_engine(_database_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline (SQL script) migrations are not supported; run against a database.")
run_migrations()
