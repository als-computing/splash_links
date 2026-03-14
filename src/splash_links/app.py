"""
FastAPI application factory for splash-links.

Usage:
    from splash_links.app import create_app

    app = create_app()                        # in-memory SQLite
    app = create_app(db_path="links.sqlite")  # persistent file
    app = create_app(db_path=os.getenv("SPLASH_LINKS_DB", ":memory:"))

The GraphQL playground is available at /graphql when the app is running.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from strawberry.fastapi import GraphQLRouter

from .schema import schema
from .store import SQLiteStore, Store, _make_engine, _url_from_path

logger = logging.getLogger(__name__)


def _run_migrations(db_url: str) -> None:
    """Stamp existing DBs and apply all pending Alembic migrations.

    Skipped for in-memory databases — they always start fresh and
    ``create_all`` inside ``SQLAlchemyStore.__init__`` is sufficient.
    """
    if ":memory:" in db_url:
        return

    from alembic.config import Config
    from sqlalchemy import inspect as sa_inspect

    from alembic import command

    here = os.path.dirname(os.path.abspath(__file__))
    ini_path = os.path.normpath(os.path.join(here, "..", "..", "..", "alembic.ini"))

    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    engine = _make_engine(db_url)
    try:
        inspector = sa_inspect(engine)
        tables = inspector.get_table_names()
        if "entities" in tables and "alembic_version" not in tables:
            logger.info("Pre-alembic database detected — stamping as head")
            command.stamp(alembic_cfg, "head")
    finally:
        engine.dispose()

    logger.info("Applying database migrations")
    command.upgrade(alembic_cfg, "head")
    logger.info("Database migrations up to date")


def create_app(db_path: Optional[str] = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        db_path: Path to the SQLite database file.  Defaults to the
                 ``SPLASH_LINKS_DB`` environment variable, falling back to
                 ``:memory:`` (ephemeral, useful for testing).
    """
    resolved_db_path = db_path or os.environ.get("SPLASH_LINKS_DB", ":memory:")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        db_url = _url_from_path(resolved_db_path)
        logger.info("Starting splash-links with database: %s", db_url)
        _run_migrations(db_url)
        store: Store = SQLiteStore(db_url)
        app.state.store = store
        try:
            yield
        finally:
            logger.info("Shutting down splash-links")
            store.close()

    async def get_context(request: Request) -> dict:
        return {"store": request.app.state.store}

    graphql_router = GraphQLRouter(
        schema,
        context_getter=get_context,
        # GraphiQL IDE enabled by default in development; set to False in prod
        graphql_ide="graphiql",
    )

    app = FastAPI(
        title="Splash Links",
        description=(
            "Entity link graph service. "
            "Store and query directional, predicate-labeled relationships "
            "between arbitrary entities via a GraphQL interface."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(graphql_router, prefix="/graphql")

    @app.get("/health", tags=["ops"], summary="Liveness check")
    def health() -> dict:
        return {"status": "ok"}

    static_dir = os.environ.get("SPLASH_LINKS_STATIC_DIR", "")
    if static_dir and os.path.isdir(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app
