"""
Module: pg_store.py
Description: PostgreSQL-backed implementation of the TripleStore interface (pgduck path).

This module provides a PostgreSQL storage backend that uses the same schema as the
DuckDB store, enabling a straightforward migration path between the two backends.
Configure it by supplying a libpq-style connection string, e.g.::

    store = PostgresStore("postgresql://user:password@host:5432/dbname")

Note: psycopg2 is a synchronous library. All blocking database calls are offloaded
to a thread-pool executor so the async event loop is not blocked.
"""

import asyncio
from datetime import datetime, timezone
from functools import partial
from typing import List, Optional

try:
    import psycopg2
    import psycopg2.extras
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "psycopg2 is required for the PostgreSQL backend. "
        "Install it with: pip install psycopg2-binary"
    ) from exc

from splash_links.models import Triple, TripleCreate, TripleFilter
from splash_links.store import TripleStore

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS triples (
    id          TEXT PRIMARY KEY,
    subject     TEXT NOT NULL,
    predicate   TEXT NOT NULL,
    object      TEXT NOT NULL,
    namespace   TEXT,
    created_at  TIMESTAMPTZ NOT NULL
);
"""

_CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_triples_subject   ON triples(subject);",
    "CREATE INDEX IF NOT EXISTS idx_triples_predicate ON triples(predicate);",
    "CREATE INDEX IF NOT EXISTS idx_triples_object    ON triples(object);",
    "CREATE INDEX IF NOT EXISTS idx_triples_namespace ON triples(namespace);",
]


class PostgresStore(TripleStore):
    """
    TripleStore implementation backed by PostgreSQL (pgduck path).

    Blocking psycopg2 calls are run in a thread-pool executor so the async
    event loop is not blocked.

    Parameters
    ----------
    dsn : str
        A libpq connection string such as
        ``"postgresql://user:password@host:5432/dbname"``.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._conn: Optional[psycopg2.extensions.connection] = None

    async def _run(self, func, *args, **kwargs):
        """Run a blocking callable in the default thread-pool executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    def _initialize_sync(self) -> None:
        self._conn = psycopg2.connect(self._dsn)
        self._conn.autocommit = False
        with self._conn.cursor() as cur:
            cur.execute(_CREATE_TABLE_SQL)
            for sql in _CREATE_INDEXES_SQL:
                cur.execute(sql)
        self._conn.commit()

    async def initialize(self) -> None:
        """Open a connection and create the schema if it does not exist."""
        await self._run(self._initialize_sync)

    def _add_triple_sync(self, triple: Triple) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO triples (id, subject, predicate, object, namespace, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    triple.id,
                    triple.subject,
                    triple.predicate,
                    triple.object,
                    triple.namespace,
                    triple.created_at,
                ),
            )
        self._conn.commit()

    async def add_triple(self, triple_in: TripleCreate) -> Triple:
        triple = Triple(**triple_in.model_dump())
        await self._run(self._add_triple_sync, triple)
        return triple

    def _get_triple_sync(self, triple_id: str) -> Optional[tuple]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, subject, predicate, object, namespace, created_at FROM triples WHERE id = %s",
                (triple_id,),
            )
            return cur.fetchone()

    async def get_triple(self, triple_id: str) -> Optional[Triple]:
        row = await self._run(self._get_triple_sync, triple_id)
        return _row_to_triple(row) if row is not None else None

    def _search_triples_sync(self, sql: str, params: List) -> list:
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    async def search_triples(self, filters: TripleFilter) -> List[Triple]:
        conditions: List[str] = []
        params: List = []

        if filters.subject is not None:
            conditions.append("subject = %s")
            params.append(filters.subject)
        if filters.predicate is not None:
            conditions.append("predicate = %s")
            params.append(filters.predicate)
        if filters.object is not None:
            conditions.append("object = %s")
            params.append(filters.object)
        if filters.namespace is not None:
            conditions.append("namespace = %s")
            params.append(filters.namespace)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"""
            SELECT id, subject, predicate, object, namespace, created_at
            FROM triples
            {where}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([filters.limit, filters.offset])

        rows = await self._run(self._search_triples_sync, sql, params)
        return [_row_to_triple(r) for r in rows]

    def _delete_triple_sync(self, triple_id: str) -> Optional[tuple]:
        with self._conn.cursor() as cur:
            cur.execute(
                "DELETE FROM triples WHERE id = %s RETURNING id",
                (triple_id,),
            )
            deleted = cur.fetchone()
        self._conn.commit()
        return deleted

    async def delete_triple(self, triple_id: str) -> bool:
        result = await self._run(self._delete_triple_sync, triple_id)
        return result is not None

    def _close_sync(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    async def close(self) -> None:
        await self._run(self._close_sync)


def _row_to_triple(row: tuple) -> Triple:
    """Convert a database row tuple to a Triple model."""
    id_, subject, predicate, object_, namespace, created_at = row
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return Triple(
        id=id_,
        subject=subject,
        predicate=predicate,
        object=object_,
        namespace=namespace,
        created_at=created_at,
    )
