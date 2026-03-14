"""
Tiled client integration for splash-links.

When a tiled node is passed to
:meth:`~splash_links.client.base.LinksClient.create_link` or
:func:`get_or_create_entity`, the node's URI is used as the canonical
identifier.  Entities are created automatically on first encounter and cached
for the lifetime of the :class:`~splash_links.client.base.LinksClient`
instance.

Stored entity properties
------------------------
For each tiled node, the following properties are captured and stored on the
splash-links entity:

* ``specs`` – list of spec names the node satisfies (when available)
* ``structure_family`` – ``"array"``, ``"table"``, ``"container"``, etc. (when available)

The entity ``uri`` already holds the full tiled node URI, so it is used
directly by :func:`from_entity` to reconnect to the node — the URI is not
duplicated in ``properties``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base import Entity

if TYPE_CHECKING:
    from .base import LinksClient


def _node_uri(node: Any) -> str:
    """
    Extract a stable URI from a tiled client node.

    Tiled nodes expose a ``.uri`` attribute with the full resource URL.
    """
    if hasattr(node, "uri"):
        return str(node.uri)
    raise TypeError(
        f"Cannot extract a URI from {type(node)!r}. Expected a tiled client node with a '.uri' attribute."
    )


def _node_name(node: Any, uri: str) -> str:
    """Derive a human-readable name from the node or the last URI segment."""
    if hasattr(node, "key"):
        return str(node.key)
    return uri.rstrip("/").rsplit("/", 1)[-1] or uri


def _node_properties(node: Any) -> dict:
    """
    Build a properties dict capturing tiled metadata for *node*.

    Keys:

    - ``specs``: list of spec names (optional, omitted when unavailable)
    - ``structure_family``: ``"array"``, ``"table"``, ``"container"``, etc.
      (optional, omitted when unavailable)
    """
    props: dict[str, Any] = {}

    try:
        specs = node.specs
        if specs:
            props["specs"] = [s.name if hasattr(s, "name") else str(s) for s in specs]
    except Exception:
        pass

    try:
        item = node.item
        structure_family = item.get("attributes", {}).get("structure_family")
        if structure_family is not None:
            props["structure_family"] = structure_family
    except Exception:
        pass

    return props


def get_or_create_entity(client: "LinksClient", node: Any) -> "Entity":
    """
    Return the :class:`~splash_links.client.base.Entity` for a tiled node,
    creating it (and caching it) if it has not been seen in this session.

    Properties capturing the server URL, path, specs, and structure family are
    stored on the entity so the node can be reconstructed later via
    :func:`from_entity`.
    """
    uri = _node_uri(node)
    if uri in client._tiled_cache:
        return client._tiled_cache[uri]

    name = _node_name(node, uri)
    props = _node_properties(node)
    entity = client.create_entity(
        entity_type="tiled",
        name=name,
        uri=uri,
        properties=props,
    )
    client._tiled_cache[uri] = entity
    return entity


def from_entity(entity: "Entity") -> Any:
    """
    Reconnect to a tiled node from a persisted
    :class:`~splash_links.client.base.Entity`.

    Uses ``entity.uri`` to call ``tiled.client.from_uri`` directly.
    Requires the :mod:`tiled` package to be installed.

    Example::

        entity = links.find_entities(entity_type="tiled")[0]
        node = from_entity(entity)
        print(node.metadata)
    """
    from tiled.client import from_uri as tiled_from_uri  # noqa: PLC0415

    if entity.uri is None:
        raise ValueError(f"Entity {entity.id!r} has no URI; cannot reconnect to a tiled node.")
    return tiled_from_uri(entity.uri)


class TiledEntity(Entity):
    """
    An :class:`~splash_links.client.base.Entity` with ``entity_type="tiled"``
    that can reconnect to the live tiled client node via :meth:`node`.

    Returned automatically by the dispatcher in
    :func:`~splash_links.client.base._entity_from_dict` whenever a fetched
    entity has ``entity_type="tiled"``.
    """

    def node(self) -> Any:
        """Return the live tiled client node for this entity."""
        return from_entity(self)
