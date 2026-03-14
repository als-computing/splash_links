import os
from logging.config import fileConfig

from alembic import context
from splash_links.store import _make_engine, _metadata, _url_from_path

# Alembic Config object
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = _metadata


def _get_url() -> str:
    """Return the DB URL: alembic.ini value, env var, or default."""
    ini_url = config.get_main_option("sqlalchemy.url", None)
    if ini_url and "://" in ini_url:
        return ini_url
    return _url_from_path(os.environ.get("SPLASH_LINKS_DB", "links.sqlite"))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout)."""
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (apply against a live DB)."""
    engine = _make_engine(_get_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
