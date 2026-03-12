"""
Module: main.py
Description: FastAPI application for the splash_links triplestore service.

Configuration via environment variables:
  STORE_BACKEND   - 'duckdb' (default) or 'postgres'
  DUCKDB_DATABASE - DuckDB file path (default: 'splash_links.duckdb')
  POSTGRES_DSN    - PostgreSQL connection string (required when STORE_BACKEND=postgres)
"""

import os
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query

from splash_links.duckdb_store import DuckDBStore
from splash_links.graphql_schema import build_graphql_router
from splash_links.models import Triple, TripleCreate, TripleFilter
from splash_links.store import TripleStore


def _create_store() -> TripleStore:
    backend = os.environ.get("STORE_BACKEND", "duckdb").lower()
    if backend == "postgres":
        dsn = os.environ.get("POSTGRES_DSN")
        if not dsn:
            raise RuntimeError("POSTGRES_DSN environment variable is required for the postgres backend.")
        from splash_links.pg_store import PostgresStore

        return PostgresStore(dsn)
    # Default: DuckDB
    db_path = os.environ.get("DUCKDB_DATABASE", "splash_links.duckdb")
    return DuckDBStore(db_path)


_store: Optional[TripleStore] = None


def get_store() -> TripleStore:
    """FastAPI dependency that returns the active TripleStore."""
    if _store is None:
        raise RuntimeError("Store has not been initialized.")  # pragma: no cover
    return _store


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _store
    _store = _create_store()
    await _store.initialize()
    yield
    await _store.close()
    _store = None


# Mount the GraphQL router at app creation so that it participates in
# FastAPI's dependency-injection (including test overrides on get_store).
_graphql_router = build_graphql_router(get_store)

app = FastAPI(
    title="splash_links",
    description=(
        "An unopinionated triplestore service for storing and searching subject–predicate–object "
        "links, backed by DuckDB or PostgreSQL and queryable via REST or GraphQL."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(_graphql_router, prefix="/graphql")


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@app.post("/triples", response_model=Triple, status_code=201, tags=["triples"])
async def create_triple(
    triple_in: TripleCreate,
    store: TripleStore = Depends(get_store),
) -> Triple:
    """Create a new triple in the store."""
    return await store.add_triple(triple_in)


@app.get("/triples/{triple_id}", response_model=Triple, tags=["triples"])
async def read_triple(
    triple_id: str,
    store: TripleStore = Depends(get_store),
) -> Triple:
    """Retrieve a single triple by its ID."""
    triple = await store.get_triple(triple_id)
    if triple is None:
        raise HTTPException(status_code=404, detail=f"Triple '{triple_id}' not found.")
    return triple


@app.get("/triples", response_model=List[Triple], tags=["triples"])
async def list_triples(
    subject: Optional[str] = Query(None, description="Filter by subject"),
    predicate: Optional[str] = Query(None, description="Filter by predicate"),
    object: Optional[str] = Query(None, description="Filter by object"),
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results to skip"),
    store: TripleStore = Depends(get_store),
) -> List[Triple]:
    """Search triples. All filters are optional and combined with AND."""
    filters = TripleFilter(
        subject=subject,
        predicate=predicate,
        object=object,
        namespace=namespace,
        limit=limit,
        offset=offset,
    )
    return await store.search_triples(filters)


@app.delete("/triples/{triple_id}", status_code=204, tags=["triples"])
async def delete_triple(
    triple_id: str,
    store: TripleStore = Depends(get_store),
) -> None:
    """Delete a triple by its ID."""
    deleted = await store.delete_triple(triple_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Triple '{triple_id}' not found.")
