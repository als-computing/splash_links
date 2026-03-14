"""
Tiled client integration for splash-links.

When a tiled node is passed to
:meth:`~splash_links.client.base.LinksClient.create_link` or
:func:`get_or_create_entity`, the node's URI is used as the canonical
identifier.  Entities are created automatically on first encounter and cached
for the lifetime of the :class:`~splash_links.client.base.LinksClient`
instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .base import Entity, LinksClient


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


def get_or_create_entity(client: "LinksClient", node: Any) -> "Entity":
    """
    Return the :class:`~splash_links.client.base.Entity` for a tiled node,
    creating it (and caching it) if it has not been seen in this session.
    """
    uri = _node_uri(node)
    if uri in client._tiled_cache:
        return client._tiled_cache[uri]

    name = _node_name(node, uri)
    entity = client.create_entity(
        entity_type="tiled",
        name=name,
        uri=uri,
    )
    client._tiled_cache[uri] = entity
    return entity
