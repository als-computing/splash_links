"""
Storage layer for the splash-links entity graph service.

The abstract `Store` interface decouples the application from the underlying
database, making it straightforward to target SQLite today and another SQL
backend later without changing the API surface.
"""

from __future__ import annotations

import abc
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Data records
# ---------------------------------------------------------------------------


class EntityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    entity_type: str
    name: str
    uri: Optional[str]
    properties: dict
    created_at: datetime


class LinkRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
        uri: Optional[str] = None,
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
    def update_entity(
        self,
        id: str,
        name: Optional[str] = None,
        uri: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> Optional[EntityRecord]: ...

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
    def update_link(self, id: str, predicate: str) -> Optional[LinkRecord]: ...

    @abc.abstractmethod
    def close(self) -> None: ...


# ---------------------------------------------------------------------------
# SQLite implementation
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS entities (
    id          TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    name        TEXT NOT NULL,
    uri         TEXT,
    properties  TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS entities_uri_idx ON entities (uri);

CREATE TABLE IF NOT EXISTS links (
    id          TEXT PRIMARY KEY,
    subject_id  TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    predicate   TEXT NOT NULL,
    object_id   TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    properties  TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

-- Compound indexes cover the multi-field combinations used by find_links.
-- The leading columns also satisfy single-field queries, so no single-column
-- indexes are needed for subject_id, predicate, or object_id.
CREATE INDEX IF NOT EXISTS entities_type_created_idx
    ON entities (entity_type, created_at);

CREATE INDEX IF NOT EXISTS links_subject_predicate_idx
    ON links (subject_id, predicate);

CREATE INDEX IF NOT EXISTS links_predicate_object_idx
    ON links (predicate, object_id);

-- Covering index for exact (subject, predicate, object) triple lookups.
CREATE INDEX IF NOT EXISTS links_triple_idx
    ON links (subject_id, predicate, object_id);
"""


class SQLiteStore(Store):
    """
    SQLite-backed store.

    A single connection is shared across the process with a lock around all
    operations so FastAPI worker threads do not race each other.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
        self._lock = threading.Lock()
        self._init_schema()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA_SQL)
            # Migrate pre-uri databases: add the column if it doesn't exist yet.
            cols = {row[1] for row in self._conn.execute("PRAGMA table_info(entities)")}
            if "uri" not in cols:
                self._conn.execute("ALTER TABLE entities ADD COLUMN uri TEXT")

    # ------------------------------------------------------------------
    # Row conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        return datetime.fromisoformat(value)

    @classmethod
    def _to_entity(cls, row: tuple) -> EntityRecord:
        id_, entity_type, name, uri, properties, created_at = row
        return EntityRecord(
            id=id_,
            entity_type=entity_type,
            name=name,
            uri=uri,
            properties=json.loads(properties) if properties else {},
            created_at=cls._parse_timestamp(created_at),
        )

    @classmethod
    def _to_link(cls, row: tuple) -> LinkRecord:
        id_, subject_id, predicate, object_id, properties, created_at = row
        return LinkRecord(
            id=id_,
            subject_id=subject_id,
            predicate=predicate,
            object_id=object_id,
            properties=json.loads(properties) if properties else {},
            created_at=cls._parse_timestamp(created_at),
        )

    @staticmethod
    def _timestamp_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Entity operations
    # ------------------------------------------------------------------

    def create_entity(
        self,
        entity_type: str,
        name: str,
        uri: Optional[str] = None,
        properties: Optional[dict] = None,
    ) -> EntityRecord:
        id_ = str(uuid.uuid4())
        created_at = self._timestamp_now()
        props_json = json.dumps(properties or {})
        with self._lock:
            self._conn.execute(
                "INSERT INTO entities (id, entity_type, name, uri, properties, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [id_, entity_type, name, uri, props_json, created_at],
            )
            row = self._conn.execute(
                "SELECT id, entity_type, name, uri, properties, created_at "
                "FROM entities WHERE id = ?",
                [id_],
            ).fetchone()
        return self._to_entity(row)

    def get_entity(self, id: str) -> Optional[EntityRecord]:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, entity_type, name, uri, properties, created_at "
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
                    "SELECT id, entity_type, name, uri, properties, created_at "
                    "FROM entities WHERE entity_type = ? "
                    "ORDER BY created_at LIMIT ? OFFSET ?",
                    [entity_type, limit, offset],
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT id, entity_type, name, uri, properties, created_at "
                    "FROM entities ORDER BY created_at LIMIT ? OFFSET ?",
                    [limit, offset],
                ).fetchall()
        return [self._to_entity(r) for r in rows]

    def delete_entity(self, id: str) -> bool:
        with self._lock:
            cursor = self._conn.execute("DELETE FROM entities WHERE id = ?", [id])
        return cursor.rowcount > 0

    def update_entity(
        self,
        id: str,
        name: Optional[str] = None,
        uri: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> Optional[EntityRecord]:
        fields, params = [], []
        if name is not None:
            fields.append("name = ?")
            params.append(name)
        if uri is not None:
            fields.append("uri = ?")
            params.append(uri)
        if entity_type is not None:
            fields.append("entity_type = ?")
            params.append(entity_type)
        if not fields:
            return self.get_entity(id)
        params.append(id)
        with self._lock:
            self._conn.execute(
                f"UPDATE entities SET {', '.join(fields)} WHERE id = ?", params
            )
            row = self._conn.execute(
                "SELECT id, entity_type, name, uri, properties, created_at FROM entities WHERE id = ?",
                [id],
            ).fetchone()
        return self._to_entity(row) if row else None

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
        if not self.get_entity(subject_id):
            raise ValueError(f"Subject entity '{subject_id}' not found")
        if not self.get_entity(object_id):
            raise ValueError(f"Object entity '{object_id}' not found")

        id_ = str(uuid.uuid4())
        created_at = self._timestamp_now()
        props_json = json.dumps(properties or {})
        with self._lock:
            self._conn.execute(
                "INSERT INTO links (id, subject_id, predicate, object_id, properties, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [id_, subject_id, predicate, object_id, props_json, created_at],
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
        params: list[str | int] = []
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
            cursor = self._conn.execute("DELETE FROM links WHERE id = ?", [id])
        return cursor.rowcount > 0

    def update_link(self, id: str, predicate: str) -> Optional[LinkRecord]:
        with self._lock:
            self._conn.execute("UPDATE links SET predicate = ? WHERE id = ?", [predicate, id])
            row = self._conn.execute(
                "SELECT id, subject_id, predicate, object_id, properties, created_at FROM links WHERE id = ?",
                [id],
            ).fetchone()
        return self._to_link(row) if row else None

    def close(self) -> None:
        self._conn.close()


DuckDBStore = SQLiteStore
