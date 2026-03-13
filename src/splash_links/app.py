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

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from strawberry.fastapi import GraphQLRouter

from .schema import schema
from .store import SQLiteStore, Store


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
        store: Store = SQLiteStore(resolved_db_path)
        app.state.store = store
        try:
            yield
        finally:
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
