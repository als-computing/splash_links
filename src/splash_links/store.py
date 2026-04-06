"""
Storage layer for the splash-links entity graph service.

The abstract ``Store`` interface decouples the application from the
underlying database.  The concrete ``SQLAlchemyStore`` targets any database
supported by SQLAlchemy 2.x — SQLite (default), PostgreSQL, and DuckDB (via
``duckdb-engine``) are the primary targets.

Connection URL examples
-----------------------
SQLite (file):     sqlite:///links.sqlite
SQLite (memory):   sqlite:///:memory:
PostgreSQL:        postgresql+psycopg2://user:pass@host/dbname
DuckDB (file):     duckdb:///links.duckdb
DuckDB (memory):   duckdb:///:memory:
"""

from __future__ import annotations

import abc
import json
import math
import struct
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    event,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator, UserDefinedType

try:
    from pgvector.psycopg2 import register_vector as register_pgvector_psycopg2
except ImportError:  # pragma: no cover - dependency may not be installed in minimal environments
    register_pgvector_psycopg2 = None

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


class EmbeddingModelRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: Optional[str]
    url: Optional[str]
    version: str


class EmbeddingRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    entity_id: str
    embedding_model_id: str
    embedding_model: EmbeddingModelRecord
    vector: list[float]
    dimensions: int
    properties: dict
    created_at: datetime


class EmbeddingMatchRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    embedding: EmbeddingRecord
    distance: float


class PostgreSQLVectorType(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **_kw) -> str:
        return "vector"


class EmbeddingVectorType(TypeDecorator):
    cache_ok = True
    impl = LargeBinary

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PostgreSQLVectorType())
        return dialect.type_descriptor(LargeBinary())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return _serialize_vector_postgresql(value)
        return _serialize_vector_blob(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            if isinstance(value, str):
                return _deserialize_vector_postgresql(value)
            return [float(item) for item in value]
        if isinstance(value, memoryview):
            value = value.tobytes()
        return _deserialize_vector_blob(value)


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
    def create_embedding_model(
        self,
        name: str,
        version: str,
        description: Optional[str] = None,
        url: Optional[str] = None,
    ) -> EmbeddingModelRecord: ...

    @abc.abstractmethod
    def get_embedding_model(self, id: str) -> Optional[EmbeddingModelRecord]: ...

    @abc.abstractmethod
    def list_embedding_models(
        self,
        name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EmbeddingModelRecord]: ...

    @abc.abstractmethod
    def delete_embedding_model(self, id: str) -> bool: ...

    @abc.abstractmethod
    def create_embedding(
        self,
        entity_id: str,
        vector: list[float],
        embedding_model_id: str,
        properties: Optional[dict] = None,
    ) -> EmbeddingRecord: ...

    @abc.abstractmethod
    def get_embedding(self, id: str) -> Optional[EmbeddingRecord]: ...

    @abc.abstractmethod
    def list_embeddings(
        self,
        entity_id: Optional[str] = None,
        embedding_model_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EmbeddingRecord]: ...

    @abc.abstractmethod
    def find_nearest_embeddings(
        self,
        query_vector: list[float],
        embedding_model_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[EmbeddingMatchRecord]: ...

    @abc.abstractmethod
    def delete_embedding(self, id: str) -> bool: ...

    @abc.abstractmethod
    def close(self) -> None: ...


# ---------------------------------------------------------------------------
# SQLAlchemy schema
# ---------------------------------------------------------------------------

_metadata = MetaData()

_entities = Table(
    "entities",
    _metadata,
    Column("id", String, primary_key=True),
    Column("entity_type", String, nullable=False),
    Column("name", String, nullable=False),
    Column("uri", String, nullable=True),
    Column("properties", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("entities_type_created_idx", "entity_type", "created_at"),
    Index("entities_uri_idx", "uri"),
)

_links = Table(
    "links",
    _metadata,
    Column("id", String, primary_key=True),
    Column("subject_id", String, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
    Column("predicate", String, nullable=False),
    Column("object_id", String, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
    Column("properties", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("links_subject_predicate_idx", "subject_id", "predicate"),
    Index("links_predicate_object_idx", "predicate", "object_id"),
    Index("links_triple_idx", "subject_id", "predicate", "object_id"),
)

_embedding_models = Table(
    "embedding_models",
    _metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("description", String, nullable=True),
    Column("url", String, nullable=True),
    Column("version", String, nullable=False),
    Index("embedding_models_name_version_idx", "name", "version", unique=True),
)

_embeddings = Table(
    "embeddings",
    _metadata,
    Column("id", String, primary_key=True),
    Column("entity_id", String, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
    Column("embedding_model_id", String, ForeignKey("embedding_models.id", ondelete="RESTRICT"), nullable=False),
    Column("vector", EmbeddingVectorType(), nullable=False),
    Column("dimensions", Integer, nullable=False),
    Column("properties", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("embeddings_entity_model_created_idx", "entity_id", "embedding_model_id", "created_at"),
    Index("embeddings_model_dimensions_idx", "embedding_model_id", "dimensions"),
)


def _normalize_vector(vector: list[float]) -> list[float]:
    if not vector:
        raise ValueError("Embedding vectors must contain at least one value")

    normalized: list[float] = []
    for value in vector:
        if isinstance(value, bool):
            raise ValueError("Embedding vectors must contain only numeric values")
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Embedding vectors must contain only numeric values") from exc
        if not math.isfinite(numeric):
            raise ValueError("Embedding vectors must contain only finite values")
        normalized.append(numeric)

    magnitude = math.sqrt(sum(value * value for value in normalized))
    if magnitude == 0.0:
        raise ValueError("Embedding vectors must not be all zeros")

    return normalized


def _serialize_vector(vector: list[float]) -> str:
    return json.dumps(vector, separators=(",", ":"))


def _deserialize_vector(value: str) -> list[float]:
    parsed = json.loads(value)
    return [float(item) for item in parsed]


def _serialize_vector_postgresql(vector: list[float]) -> str:
    return _serialize_vector(vector)


def _deserialize_vector_postgresql(value: str) -> list[float]:
    return _deserialize_vector(value)


def _serialize_vector_blob(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def _deserialize_vector_blob(value: bytes) -> list[float]:
    if len(value) % 4 != 0:
        raise ValueError("Stored embedding blob has an invalid length")
    dimensions = len(value) // 4
    return list(struct.unpack(f"<{dimensions}f", value))


def _cosine_distance(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding vectors must have the same number of dimensions")

    dot = sum(lhs * rhs for lhs, rhs in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return 1.0 - (dot / (left_norm * right_norm))


def _embedding_select():
    return select(
        _embeddings.c.id,
        _embeddings.c.entity_id,
        _embeddings.c.embedding_model_id,
        _embeddings.c.vector,
        _embeddings.c.dimensions,
        _embeddings.c.properties,
        _embeddings.c.created_at,
        _embedding_models.c.name.label("embedding_model_name"),
        _embedding_models.c.description.label("embedding_model_description"),
        _embedding_models.c.url.label("embedding_model_url"),
        _embedding_models.c.version.label("embedding_model_version"),
    ).select_from(_embeddings.join(_embedding_models, _embeddings.c.embedding_model_id == _embedding_models.c.id))


def _make_engine(db_url: str) -> Engine:
    """Create a SQLAlchemy engine from a URL, applying dialect-specific tuning."""
    is_sqlite = db_url.startswith("sqlite")
    is_memory = ":memory:" in db_url

    kwargs: dict = {}
    if is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False}
    if is_memory:
        kwargs["poolclass"] = StaticPool

    engine = create_engine(db_url, **kwargs)

    if is_sqlite:
        # Enable foreign-key enforcement for every new SQLite connection.
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(conn, _record):
            conn.execute("PRAGMA foreign_keys=ON")

    if engine.dialect.name == "postgresql" and register_pgvector_psycopg2 is not None:
        @event.listens_for(engine, "connect")
        def _register_pgvector(conn, _record):
            register_pgvector_psycopg2(conn)

    return engine


def _url_from_path(db_path: str) -> str:
    """Convert a plain file path / ':memory:' to a sqlite:// URL."""
    if "://" in db_path:
        return db_path
    if db_path == ":memory:":
        return "sqlite:///:memory:"
    return f"sqlite:///{db_path}"


# ---------------------------------------------------------------------------
# SQLAlchemy implementation
# ---------------------------------------------------------------------------


class SQLAlchemyStore(Store):
    """
    Database-agnostic store backed by SQLAlchemy Core.

    ``db_url`` may be any SQLAlchemy connection URL.  For convenience,
    plain file paths and ``':memory:'`` are auto-converted to
    ``sqlite:///…`` / ``sqlite:///:memory:``.
    """

    def __init__(self, db_url: str = ":memory:") -> None:
        self._engine: Engine = _make_engine(_url_from_path(db_url))
        _metadata.create_all(self._engine)

    # ------------------------------------------------------------------
    # Row conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_entity(row) -> EntityRecord:
        return EntityRecord(
            id=row.id,
            entity_type=row.entity_type,
            name=row.name,
            uri=row.uri,
            properties=row.properties or {},
            created_at=row.created_at,
        )

    @staticmethod
    def _to_link(row) -> LinkRecord:
        return LinkRecord(
            id=row.id,
            subject_id=row.subject_id,
            predicate=row.predicate,
            object_id=row.object_id,
            properties=row.properties or {},
            created_at=row.created_at,
        )

    @staticmethod
    def _to_embedding_model(row) -> EmbeddingModelRecord:
        mapping = row._mapping if hasattr(row, "_mapping") else row
        return EmbeddingModelRecord(
            id=mapping["id"],
            name=mapping["name"],
            description=mapping["description"],
            url=mapping["url"],
            version=mapping["version"],
        )

    @staticmethod
    def _to_embedding(row) -> EmbeddingRecord:
        mapping = row._mapping if hasattr(row, "_mapping") else row
        vector = mapping["vector"]
        if isinstance(vector, str):
            vector = _deserialize_vector_postgresql(vector)
        elif isinstance(vector, (bytes, memoryview)):
            blob = vector.tobytes() if isinstance(vector, memoryview) else vector
            vector = _deserialize_vector_blob(blob)
        else:
            vector = [float(item) for item in vector]
        return EmbeddingRecord(
            id=mapping["id"],
            entity_id=mapping["entity_id"],
            embedding_model_id=mapping["embedding_model_id"],
            embedding_model=EmbeddingModelRecord(
                id=mapping["embedding_model_id"],
                name=mapping["embedding_model_name"],
                description=mapping["embedding_model_description"],
                url=mapping["embedding_model_url"],
                version=mapping["embedding_model_version"],
            ),
            vector=vector,
            dimensions=mapping["dimensions"],
            properties=mapping["properties"] or {},
            created_at=mapping["created_at"],
        )

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
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            conn.execute(
                insert(_entities).values(
                    id=id_,
                    entity_type=entity_type,
                    name=name,
                    uri=uri,
                    properties=properties or {},
                    created_at=now,
                )
            )
            row = conn.execute(select(_entities).where(_entities.c.id == id_)).one()
        return self._to_entity(row)

    def get_entity(self, id: str) -> Optional[EntityRecord]:
        with self._engine.connect() as conn:
            row = conn.execute(select(_entities).where(_entities.c.id == id)).one_or_none()
        return self._to_entity(row) if row else None

    def list_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntityRecord]:
        stmt = select(_entities).order_by(_entities.c.created_at).limit(limit).offset(offset)
        if entity_type is not None:
            stmt = stmt.where(_entities.c.entity_type == entity_type)
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).all()
        return [self._to_entity(r) for r in rows]

    def delete_entity(self, id: str) -> bool:
        with self._engine.begin() as conn:
            result = conn.execute(delete(_entities).where(_entities.c.id == id))
        return result.rowcount > 0

    def update_entity(
        self,
        id: str,
        name: Optional[str] = None,
        uri: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> Optional[EntityRecord]:
        values: dict = {}
        if name is not None:
            values["name"] = name
        if uri is not None:
            values["uri"] = uri
        if entity_type is not None:
            values["entity_type"] = entity_type
        with self._engine.begin() as conn:
            if values:
                conn.execute(update(_entities).where(_entities.c.id == id).values(**values))
            row = conn.execute(select(_entities).where(_entities.c.id == id)).one_or_none()
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
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            conn.execute(
                insert(_links).values(
                    id=id_,
                    subject_id=subject_id,
                    predicate=predicate,
                    object_id=object_id,
                    properties=properties or {},
                    created_at=now,
                )
            )
            row = conn.execute(select(_links).where(_links.c.id == id_)).one()
        return self._to_link(row)

    def get_link(self, id: str) -> Optional[LinkRecord]:
        with self._engine.connect() as conn:
            row = conn.execute(select(_links).where(_links.c.id == id)).one_or_none()
        return self._to_link(row) if row else None

    def find_links(
        self,
        subject_id: Optional[str] = None,
        predicate: Optional[str] = None,
        object_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[LinkRecord]:
        stmt = select(_links).order_by(_links.c.created_at).limit(limit).offset(offset)
        if subject_id is not None:
            stmt = stmt.where(_links.c.subject_id == subject_id)
        if predicate is not None:
            stmt = stmt.where(_links.c.predicate == predicate)
        if object_id is not None:
            stmt = stmt.where(_links.c.object_id == object_id)
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).all()
        return [self._to_link(r) for r in rows]

    def delete_link(self, id: str) -> bool:
        with self._engine.begin() as conn:
            result = conn.execute(delete(_links).where(_links.c.id == id))
        return result.rowcount > 0

    def update_link(self, id: str, predicate: str) -> Optional[LinkRecord]:
        with self._engine.begin() as conn:
            conn.execute(update(_links).where(_links.c.id == id).values(predicate=predicate))
            row = conn.execute(select(_links).where(_links.c.id == id)).one_or_none()
        return self._to_link(row) if row else None

    # ------------------------------------------------------------------
    # Embedding operations
    # ------------------------------------------------------------------

    def create_embedding(
        self,
        entity_id: str,
        vector: list[float],
        embedding_model: str = "default",
        properties: Optional[dict] = None,
    ) -> EmbeddingRecord:
        if not self.get_entity(entity_id):
            raise ValueError(f"Entity '{entity_id}' not found")

        normalized_vector = _normalize_vector(vector)
        id_ = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            conn.execute(
                insert(_embeddings).values(
                    id=id_,
                    entity_id=entity_id,
                    embedding_model=embedding_model,
                    vector=normalized_vector,
                    dimensions=len(normalized_vector),
                    properties=properties or {},
                    created_at=now,
                )
            )
            row = conn.execute(select(_embeddings).where(_embeddings.c.id == id_)).one()
        return self._to_embedding(row)

    def get_embedding(self, id: str) -> Optional[EmbeddingRecord]:
        with self._engine.connect() as conn:
            row = conn.execute(select(_embeddings).where(_embeddings.c.id == id)).one_or_none()
        return self._to_embedding(row) if row else None

    def list_embeddings(
        self,
        entity_id: Optional[str] = None,
        embedding_model: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EmbeddingRecord]:
        stmt = select(_embeddings).order_by(_embeddings.c.created_at).limit(limit).offset(offset)
        if entity_id is not None:
            stmt = stmt.where(_embeddings.c.entity_id == entity_id)
        if embedding_model is not None:
            stmt = stmt.where(_embeddings.c.embedding_model == embedding_model)
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).all()
        return [self._to_embedding(row) for row in rows]

    def find_nearest_embeddings(
        self,
        query_vector: list[float],
        embedding_model: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[EmbeddingMatchRecord]:
        normalized_query = _normalize_vector(query_vector)
        if self._engine.dialect.name == "postgresql":
            return self._find_nearest_embeddings_postgresql(
                query_vector=normalized_query,
                embedding_model=embedding_model,
                entity_id=entity_id,
                limit=limit,
                offset=offset,
            )
        return self._find_nearest_embeddings_python(
            query_vector=normalized_query,
            embedding_model=embedding_model,
            entity_id=entity_id,
            limit=limit,
            offset=offset,
        )

    def _find_nearest_embeddings_python(
        self,
        query_vector: list[float],
        embedding_model: Optional[str],
        entity_id: Optional[str],
        limit: int,
        offset: int,
    ) -> list[EmbeddingMatchRecord]:
        stmt = select(_embeddings).where(_embeddings.c.dimensions == len(query_vector))
        if entity_id is not None:
            stmt = stmt.where(_embeddings.c.entity_id == entity_id)
        if embedding_model is not None:
            stmt = stmt.where(_embeddings.c.embedding_model == embedding_model)

        with self._engine.connect() as conn:
            rows = conn.execute(stmt).all()

        matches = [
            EmbeddingMatchRecord(
                embedding=record,
                distance=_cosine_distance(record.vector, query_vector),
            )
            for record in (self._to_embedding(row) for row in rows)
        ]
        matches.sort(key=lambda match: (match.distance, match.embedding.created_at, match.embedding.id))
        return matches[offset : offset + limit]

    def _find_nearest_embeddings_postgresql(
        self,
        query_vector: list[float],
        embedding_model: Optional[str],
        entity_id: Optional[str],
        limit: int,
        offset: int,
    ) -> list[EmbeddingMatchRecord]:
        conditions = ["dimensions = :dimensions"]
        params: dict[str, object] = {
            "dimensions": len(query_vector),
            "query_vector": _serialize_vector(query_vector),
            "limit": limit,
            "offset": offset,
        }
        if entity_id is not None:
            conditions.append("entity_id = :entity_id")
            params["entity_id"] = entity_id
        if embedding_model is not None:
            conditions.append("embedding_model = :embedding_model")
            params["embedding_model"] = embedding_model

        sql = f"""
            SELECT
                id,
                entity_id,
                embedding_model,
                vector,
                dimensions,
                properties,
                created_at,
                CAST(vector AS vector) <=> CAST(:query_vector AS vector) AS distance
            FROM embeddings
            WHERE {' AND '.join(conditions)}
            ORDER BY distance, created_at, id
            LIMIT :limit
            OFFSET :offset
        """

        with self._engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()

        return [
            EmbeddingMatchRecord(
                embedding=self._to_embedding(row),
                distance=float(row["distance"]),
            )
            for row in rows
        ]

    def delete_embedding(self, id: str) -> bool:
        with self._engine.begin() as conn:
            result = conn.execute(delete(_embeddings).where(_embeddings.c.id == id))
        return result.rowcount > 0

    def close(self) -> None:
        self._engine.dispose()


# Backward-compatible aliases
SQLiteStore = SQLAlchemyStore
DuckDBStore = SQLAlchemyStore
