"""
Storage layer for the splash-links entity graph service.

The abstract `Store` interface decouples the application from the underlying
database, making it straightforward to swap DuckDB for pgduck (Postgres +
DuckDB extension) or any other SQL backend in the future.
"""

from __future__ import annotations

import abc
import json
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import duckdb

# ---------------------------------------------------------------------------
# Data records (plain dataclasses, not Pydantic, to stay dependency-light)
# ---------------------------------------------------------------------------


@dataclass
class EntityRecord:
    id: str
    entity_type: str
    name: str
    properties: dict
    created_at: datetime


@dataclass
class LinkRecord:
    id: str
    subject_id: str
    predicate: str
    object_id: str
    properties: dict
    created_at: datetime


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class Store(abc.ABC):
    """Minimal interface for entity/link persistence."""

    @abc.abstractmethod
    def create_entity(
        self,
        entity_type: str,
        name: str,
        properties: Optional[dict] = None,
    ) -> EntityRecord: ...

    @abc.abstractmethod
    def get_entity(self, id: str) -> Optional[EntityRecord]: ...

    @abc.abstractmethod
    def list_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntityRecord]: ...

    @abc.abstractmethod
    def delete_entity(self, id: str) -> bool: ...

    @abc.abstractmethod
    def create_link(
        self,
        subject_id: str,
        predicate: str,
        object_id: str,
        properties: Optional[dict] = None,
    ) -> LinkRecord: ...

    @abc.abstractmethod
    def get_link(self, id: str) -> Optional[LinkRecord]: ...

    @abc.abstractmethod
    def find_links(
        self,
        subject_id: Optional[str] = None,
        predicate: Optional[str] = None,
        object_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[LinkRecord]: ...

    @abc.abstractmethod
    def delete_link(self, id: str) -> bool: ...

    @abc.abstractmethod
    def close(self) -> None: ...


# ---------------------------------------------------------------------------
# DuckDB implementation
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entities (
    id          TEXT        PRIMARY KEY,
    entity_type TEXT        NOT NULL,
    name        TEXT        NOT NULL,
    properties  JSON,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS links (
    id          TEXT        PRIMARY KEY,
    subject_id  TEXT        NOT NULL,
    predicate   TEXT        NOT NULL,
    object_id   TEXT        NOT NULL,
    properties  JSON,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS links_subject_idx   ON links (subject_id);
CREATE INDEX IF NOT EXISTS links_object_idx    ON links (object_id);
CREATE INDEX IF NOT EXISTS links_predicate_idx ON links (predicate);
"""


class DuckDBStore(Store):
    """
    DuckDB-backed store.

    Thread-safety: DuckDB's in-process mode allows concurrent reads; we guard
    writes with a lock so FastAPI's thread-pool workers don't collide.

    pgduck migration path: Replace ``duckdb.connect`` with a connection that
    uses DuckDB's ``postgres_scan`` / ``ATTACH`` extension, or drop in a
    postgres-dialect store that implements the same ``Store`` ABC.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = duckdb.connect(db_path)
        self._lock = threading.Lock()
        self._init_schema()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._lock:
            for stmt in _SCHEMA_SQL.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    self._conn.execute(stmt)

    # ------------------------------------------------------------------
    # Row conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_entity(row: tuple) -> EntityRecord:
        id_, entity_type, name, properties, created_at = row
        if isinstance(properties, str):
            properties = json.loads(properties) if properties else {}
        return EntityRecord(
            id=id_,
            entity_type=entity_type,
            name=name,
            properties=properties or {},
            created_at=created_at,
        )

    @staticmethod
    def _to_link(row: tuple) -> LinkRecord:
        id_, subject_id, predicate, object_id, properties, created_at = row
        if isinstance(properties, str):
            properties = json.loads(properties) if properties else {}
        return LinkRecord(
            id=id_,
            subject_id=subject_id,
            predicate=predicate,
            object_id=object_id,
            properties=properties or {},
            created_at=created_at,
        )

    # ------------------------------------------------------------------
    # Entity operations
    # ------------------------------------------------------------------

    def create_entity(
        self,
        entity_type: str,
        name: str,
        properties: Optional[dict] = None,
    ) -> EntityRecord:
        id_ = str(uuid.uuid4())
        props_json = json.dumps(properties or {})
        with self._lock:
            self._conn.execute(
                "INSERT INTO entities (id, entity_type, name, properties) "
                "VALUES (?, ?, ?, ?::JSON)",
                [id_, entity_type, name, props_json],
            )
            row = self._conn.execute(
                "SELECT id, entity_type, name, properties, created_at "
                "FROM entities WHERE id = ?",
                [id_],
            ).fetchone()
        return self._to_entity(row)

    def get_entity(self, id: str) -> Optional[EntityRecord]:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, entity_type, name, properties, created_at "
                "FROM entities WHERE id = ?",
                [id],
            ).fetchone()
        return self._to_entity(row) if row else None

    def list_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntityRecord]:
        with self._lock:
            if entity_type:
                rows = self._conn.execute(
                    "SELECT id, entity_type, name, properties, created_at "
                    "FROM entities WHERE entity_type = ? "
                    "ORDER BY created_at LIMIT ? OFFSET ?",
                    [entity_type, limit, offset],
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT id, entity_type, name, properties, created_at "
                    "FROM entities ORDER BY created_at LIMIT ? OFFSET ?",
                    [limit, offset],
                ).fetchall()
        return [self._to_entity(r) for r in rows]

    def delete_entity(self, id: str) -> bool:
        """Delete an entity and cascade-remove all its links."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM links WHERE subject_id = ? OR object_id = ?",
                [id, id],
            )
            result = self._conn.execute(
                "DELETE FROM entities WHERE id = ? RETURNING id", [id]
            ).fetchone()
        return result is not None

    # ------------------------------------------------------------------
    # Link operations
    # ------------------------------------------------------------------

    def create_link(
        self,
        subject_id: str,
        predicate: str,
        object_id: str,
        properties: Optional[dict] = None,
    ) -> LinkRecord:
        # Validate both endpoints exist before inserting.
        if not self.get_entity(subject_id):
            raise ValueError(f"Subject entity '{subject_id}' not found")
        if not self.get_entity(object_id):
            raise ValueError(f"Object entity '{object_id}' not found")

        id_ = str(uuid.uuid4())
        props_json = json.dumps(properties or {})
        with self._lock:
            self._conn.execute(
                "INSERT INTO links (id, subject_id, predicate, object_id, properties) "
                "VALUES (?, ?, ?, ?, ?::JSON)",
                [id_, subject_id, predicate, object_id, props_json],
            )
            row = self._conn.execute(
                "SELECT id, subject_id, predicate, object_id, properties, created_at "
                "FROM links WHERE id = ?",
                [id_],
            ).fetchone()
        return self._to_link(row)

    def get_link(self, id: str) -> Optional[LinkRecord]:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, subject_id, predicate, object_id, properties, created_at "
                "FROM links WHERE id = ?",
                [id],
            ).fetchone()
        return self._to_link(row) if row else None

    def find_links(
        self,
        subject_id: Optional[str] = None,
        predicate: Optional[str] = None,
        object_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[LinkRecord]:
        conditions: list[str] = []
        params: list = []
        if subject_id is not None:
            conditions.append("subject_id = ?")
            params.append(subject_id)
        if predicate is not None:
            conditions.append("predicate = ?")
            params.append(predicate)
        if object_id is not None:
            conditions.append("object_id = ?")
            params.append(object_id)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.extend([limit, offset])

        with self._lock:
            rows = self._conn.execute(
                f"SELECT id, subject_id, predicate, object_id, properties, created_at "
                f"FROM links {where} ORDER BY created_at LIMIT ? OFFSET ?",
                params,
            ).fetchall()
        return [self._to_link(r) for r in rows]

    def delete_link(self, id: str) -> bool:
        with self._lock:
            result = self._conn.execute(
                "DELETE FROM links WHERE id = ? RETURNING id", [id]
            ).fetchone()
        return result is not None

    def close(self) -> None:
        self._conn.close()
