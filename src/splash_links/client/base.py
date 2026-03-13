"""
HTTP client for the splash-links GraphQL service.

Usage::

    from splash_links.client.base import from_uri

    links = from_uri("splash://localhost:8080")
    entity = links.create_entity(entity_type="Sample", properties={"name": "SAXS Run 1"})
    entity2 = links.create_entity(entity_type="Sample", properties={"name": "Processed 1"})
    link = links.create_link(entity, "processed_from", entity2)
    links.find_links(entity)  # all links involving entity
"""
from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class Entity(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    entity_type: str = Field(alias="entityType")
    name: str
    uri: Optional[str] = None
    properties: Optional[dict]
    created_at: str = Field(alias="createdAt")


class Link(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    subject_id: str = Field(alias="subjectId")
    predicate: str
    object_id: str = Field(alias="objectId")
    properties: Optional[dict]
    created_at: str = Field(alias="createdAt")


# ---------------------------------------------------------------------------
# GraphQL operations
# ---------------------------------------------------------------------------

_ENTITY_FIELDS = "id entityType name uri properties createdAt"
_LINK_FIELDS = "id subjectId predicate objectId properties createdAt"

_CREATE_ENTITY_MUTATION = f"""
mutation CreateEntity($input: CreateEntityInput!) {{
  createEntity(input: $input) {{ {_ENTITY_FIELDS} }}
}}
"""

_CREATE_LINK_MUTATION = f"""
mutation CreateLink($input: CreateLinkInput!) {{
  createLink(input: $input) {{ {_LINK_FIELDS} }}
}}
"""

_FIND_LINKS_QUERY = f"""
query FindLinks($subjectId: ID, $objectId: ID, $predicate: String, $limit: Int, $offset: Int) {{
  asSubject: links(subjectId: $subjectId, predicate: $predicate, limit: $limit, offset: $offset) {{
    {_LINK_FIELDS}
  }}
  asObject: links(objectId: $objectId, predicate: $predicate, limit: $limit, offset: $offset) {{
    {_LINK_FIELDS}
  }}
}}
"""


# ---------------------------------------------------------------------------
# Record -> model helpers
# ---------------------------------------------------------------------------


def _entity_from_dict(d: dict) -> Entity:
    return Entity.model_validate(d)


def _link_from_dict(d: dict) -> Link:
    return Link.model_validate(d)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class LinksClient:
    """
    Synchronous HTTP client for the splash-links GraphQL API.

    Instantiate via :func:`from_uri` rather than directly.
    """

    def __init__(self, base_url: str) -> None:
        self._gql_url = base_url.rstrip("/") + "/graphql"
        # Cache: tiled node URI -> Entity, avoids duplicate entity creation
        self._tiled_cache: dict[str, Entity] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _execute(self, query: str, variables: Optional[dict] = None) -> dict:
        resp = httpx.post(
            self._gql_url,
            json={"query": query, "variables": variables or {}},
            timeout=30.0,
        )
        resp.raise_for_status()
        body = resp.json()
        if "errors" in body:
            raise RuntimeError(f"GraphQL error: {body['errors']}")
        return body["data"]

    def _resolve(self, obj: Any) -> str:
        """Return the entity ID for an Entity, a string ID, or a tiled node."""
        if isinstance(obj, Entity):
            return obj.id
        if isinstance(obj, str):
            return obj
        # Assume tiled node - lazy import to avoid hard dependency
        from .tiled import get_or_create_entity

        return get_or_create_entity(self, obj).id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_entity(
        self,
        entity_type: str,
        properties: Optional[dict] = None,
        name: Optional[str] = None,
        uri: Optional[str] = None,
    ) -> Entity:
        """
        Create an entity on the server.

        ``name`` is extracted from *properties* if not supplied separately.
        Falls back to *entity_type* when no name can be determined.
        """
        props = dict(properties or {})
        resolved_name = name or props.pop("name", entity_type)
        data = self._execute(
            _CREATE_ENTITY_MUTATION,
            {
                "input": {
                    "entityType": entity_type,
                    "name": resolved_name,
                    "uri": uri,
                    "properties": props or None,
                }
            },
        )
        return _entity_from_dict(data["createEntity"])

    def create_link(
        self,
        subject_id: Any,
        predicate: str,
        object_id: Any,
        properties: Optional[dict] = None,
    ) -> Link:
        """
        Create a directed link between two entities.

        *subject_id* and *object_id* may be:

        * an :class:`Entity` returned by :meth:`create_entity`
        * a raw entity ID string
        * a tiled client node (entity is auto-created on first encounter)
        """
        sid = self._resolve(subject_id)
        oid = self._resolve(object_id)
        data = self._execute(
            _CREATE_LINK_MUTATION,
            {
                "input": {
                    "subjectId": sid,
                    "predicate": predicate,
                    "objectId": oid,
                    "properties": properties,
                }
            },
        )
        return _link_from_dict(data["createLink"])

    def find_links(
        self,
        entity: Any,
        predicate: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Link]:
        """
        Return all links where *entity* appears as subject or object.

        Optionally filter by *predicate*.
        """
        entity_id = self._resolve(entity)
        data = self._execute(
            _FIND_LINKS_QUERY,
            {
                "subjectId": entity_id,
                "objectId": entity_id,
                "predicate": predicate,
                "limit": limit,
                "offset": offset,
            },
        )
        seen: set[str] = set()
        links: list[Link] = []
        for record in data["asSubject"] + data["asObject"]:
            if record["id"] not in seen:
                seen.add(record["id"])
                links.append(_link_from_dict(record))
        return links


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def from_uri(uri: str) -> LinksClient:
    """
    Create a :class:`LinksClient` from a URI.

    Supported schemes:

    * ``splash://host:port``  ->  ``http://host:port``
    * ``http://host:port``
    * ``https://host:port``

    Example::

        links = from_uri("splash://localhost:8080")
    """
    parsed = urlparse(uri)
    if parsed.scheme == "splash":
        base_url = f"http://{parsed.netloc}"
    elif parsed.scheme in ("http", "https"):
        base_url = f"{parsed.scheme}://{parsed.netloc}"
    else:
        raise ValueError(
            f"Unsupported URI scheme {parsed.scheme!r}. "
            "Use 'splash://', 'http://', or 'https://'."
        )
    return LinksClient(base_url)
