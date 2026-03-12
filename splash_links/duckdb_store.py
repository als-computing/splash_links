"""
Module: duckdb_store.py
Description: DuckDB-backed implementation of the TripleStore interface.
"""

import threading
from datetime import datetime, timezone
from typing import List, Optional

import duckdb

from splash_links.models import Triple, TripleCreate, TripleFilter
from splash_links.store import TripleStore

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS triples (
    id          VARCHAR PRIMARY KEY,
    subject     VARCHAR NOT NULL,
    predicate   VARCHAR NOT NULL,
    object      VARCHAR NOT NULL,
    namespace   VARCHAR,
    created_at  TIMESTAMPTZ NOT NULL
);
"""

_CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_triples_subject   ON triples(subject);",
    "CREATE INDEX IF NOT EXISTS idx_triples_predicate ON triples(predicate);",
    "CREATE INDEX IF NOT EXISTS idx_triples_object    ON triples(object);",
    "CREATE INDEX IF NOT EXISTS idx_triples_namespace ON triples(namespace);",
]


class DuckDBStore(TripleStore):
    """
    TripleStore implementation backed by DuckDB.

    Parameters
    ----------
    database : str
        Path to the DuckDB database file, or ``':memory:'`` for an in-memory
        database (useful for testing).
    """

    def __init__(self, database: str = ":memory:") -> None:
        self._database = database
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        self._lock = threading.Lock()

    async def initialize(self) -> None:
        """Create the schema if it does not already exist."""
        self._conn = duckdb.connect(self._database)
        self._conn.execute(_CREATE_TABLE_SQL)
        for sql in _CREATE_INDEXES_SQL:
            self._conn.execute(sql)

    async def add_triple(self, triple_in: TripleCreate) -> Triple:
        triple = Triple(**triple_in.model_dump())
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO triples (id, subject, predicate, object, namespace, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    triple.id,
                    triple.subject,
                    triple.predicate,
                    triple.object,
                    triple.namespace,
                    triple.created_at,
                ],
            )
        return triple

    async def get_triple(self, triple_id: str) -> Optional[Triple]:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, subject, predicate, object, namespace, created_at FROM triples WHERE id = ?",
                [triple_id],
            ).fetchone()
        if row is None:
            return None
        return _row_to_triple(row)

    async def search_triples(self, filters: TripleFilter) -> List[Triple]:
        conditions: List[str] = []
        params: List = []

        if filters.subject is not None:
            conditions.append("subject = ?")
            params.append(filters.subject)
        if filters.predicate is not None:
            conditions.append("predicate = ?")
            params.append(filters.predicate)
        if filters.object is not None:
            conditions.append("object = ?")
            params.append(filters.object)
        if filters.namespace is not None:
            conditions.append("namespace = ?")
            params.append(filters.namespace)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"""
            SELECT id, subject, predicate, object, namespace, created_at
            FROM triples
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([filters.limit, filters.offset])

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_triple(r) for r in rows]

    async def delete_triple(self, triple_id: str) -> bool:
        with self._lock:
            result = self._conn.execute(
                "DELETE FROM triples WHERE id = ? RETURNING id", [triple_id]
            ).fetchone()
        return result is not None

    async def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


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
