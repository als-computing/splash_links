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

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from strawberry.fastapi import GraphQLRouter

from .schema import schema
from .store import SQLAlchemyStore as SQLiteStore
from .store import EmbeddingRecord, Store, _make_engine, _url_from_path

logger = logging.getLogger(__name__)


class EmbeddingPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    entity_id: str = Field(alias="entityId")
    embedding_model: str = Field(alias="embeddingModel")
    vector: list[float]
    dimensions: int
    properties: dict
    created_at: str = Field(alias="createdAt")


class CreateEmbeddingPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    entity_id: str = Field(alias="entityId")
    vector: list[float]
    embedding_model: str = Field(default="default", alias="embeddingModel")
    properties: Optional[dict] = None


def _embedding_payload(record: EmbeddingRecord) -> EmbeddingPayload:
    return EmbeddingPayload(
        id=record.id,
        entity_id=record.entity_id,
        embedding_model=record.embedding_model,
        vector=record.vector,
        dimensions=record.dimensions,
        properties=record.properties,
        created_at=record.created_at.isoformat(),
    )


def _embedding_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = status.HTTP_404_NOT_FOUND if "not found" in message.lower() else status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=status_code, detail=message)


def _run_migrations(db_url: str) -> None:
    """Stamp existing DBs and apply all pending Alembic migrations.

    Skipped for in-memory databases — they always start fresh and
    ``create_all`` inside ``SQLAlchemyStore.__init__`` is sufficient.
    """
    if ":memory:" in db_url:
        return

    from alembic.config import Config

    from alembic import command

    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(here, "..", ".."))
    alembic_dir = os.path.join(project_root, "alembic")

    # Don't pass ini_path to Config — avoids fileConfig() reconfiguring
    # the logging system mid-app (which can interfere with uvicorn's handlers).
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", alembic_dir)
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Use a context manager so the connection is definitely closed and the
    # write lock released before alembic opens its own connection.
    engine = _make_engine(db_url)
    try:
        with engine.connect() as conn:
            from sqlalchemy import inspect as sa_inspect

            table_names = sa_inspect(conn).get_table_names()
            if "entities" in table_names and "alembic_version" not in table_names:
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

    app.include_router(graphql_router, prefix="/splash_links/graphql")

    @app.get("/splash_links/health", tags=["ops"], summary="Liveness check")
    def health() -> dict:
        return {"status": "ok"}

    @app.post(
        "/splash_links/embeddings",
        response_model=EmbeddingPayload,
        status_code=status.HTTP_201_CREATED,
        tags=["embeddings"],
        summary="Create an embedding",
    )
    def create_embedding(payload: CreateEmbeddingPayload, request: Request) -> EmbeddingPayload:
        try:
            record = request.app.state.store.create_embedding(
                entity_id=payload.entity_id,
                vector=payload.vector,
                embedding_model=payload.embedding_model,
                properties=payload.properties,
            )
        except ValueError as exc:
            raise _embedding_error(exc) from exc
        return _embedding_payload(record)

    @app.get(
        "/splash_links/embeddings/{embedding_id}",
        response_model=EmbeddingPayload,
        tags=["embeddings"],
        summary="Fetch one embedding",
    )
    def get_embedding(embedding_id: str, request: Request) -> EmbeddingPayload:
        record = request.app.state.store.get_embedding(embedding_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Embedding not found")
        return _embedding_payload(record)

    @app.get(
        "/splash_links/embeddings",
        response_model=list[EmbeddingPayload],
        tags=["embeddings"],
        summary="List embeddings",
    )
    def list_embeddings(
        request: Request,
        entity_id: Optional[str] = Query(None, alias="entityId"),
        embedding_model: Optional[str] = Query(None, alias="embeddingModel"),
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ) -> list[EmbeddingPayload]:
        records = request.app.state.store.list_embeddings(
            entity_id=entity_id,
            embedding_model=embedding_model,
            limit=limit,
            offset=offset,
        )
        return [_embedding_payload(record) for record in records]

    @app.delete(
        "/splash_links/embeddings/{embedding_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["embeddings"],
        summary="Delete one embedding",
    )
    def delete_embedding(embedding_id: str, request: Request) -> Response:
        deleted = request.app.state.store.delete_embedding(embedding_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Embedding not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    static_dir = os.environ.get("SPLASH_LINKS_STATIC_DIR", "")
    if static_dir and os.path.isdir(static_dir):
        app.mount("/splash_links", StaticFiles(directory=static_dir, html=True), name="static")

    return app
