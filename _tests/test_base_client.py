from __future__ import annotations

import pytest

from splash_links.client import base as base_module
from splash_links.client import tiled as tiled_module
from splash_links.client.base import Entity, LinksClient, from_uri
from splash_links.client.tiled import _node_name, _node_uri
from splash_links.client.tiled import get_or_create_entity as tiled_get_or_create


class FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_from_uri_supports_expected_schemes():
    assert from_uri("splash://localhost:8080")._gql_url == "http://localhost:8080/graphql"
    assert from_uri("http://example.com")._gql_url == "http://example.com/graphql"
    assert from_uri("https://example.com")._gql_url == "https://example.com/graphql"

    with pytest.raises(ValueError, match="Unsupported URI scheme"):
        from_uri("ftp://example.com")


def test_execute_raises_on_graphql_errors(monkeypatch):
    monkeypatch.setattr(
        base_module.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse({"errors": [{"message": "boom"}]}),
    )

    client = LinksClient("http://example.com")

    with pytest.raises(RuntimeError, match="GraphQL error"):
        client._execute("query { ping }")


def test_create_entity_posts_expected_payload(monkeypatch):
    seen: dict[str, object] = {}

    def fake_post(url: str, json: dict, timeout: float):
        seen["url"] = url
        seen["json"] = json
        seen["timeout"] = timeout
        return FakeResponse(
            {
                "data": {
                    "createEntity": {
                        "id": "ent-1",
                        "entityType": "Sample",
                        "name": "SAXS Run 1",
                        "properties": {"beamline": "12.3.1"},
                        "createdAt": "2026-01-01T00:00:00Z",
                    }
                }
            }
        )

    monkeypatch.setattr(base_module.httpx, "post", fake_post)

    client = from_uri("splash://api:8080")
    entity = client.create_entity("Sample", {"name": "SAXS Run 1", "beamline": "12.3.1"})

    assert entity.id == "ent-1"
    assert seen["url"] == "http://api:8080/graphql"
    assert seen["timeout"] == 30.0
    assert seen["json"] == {
        "query": base_module._CREATE_ENTITY_MUTATION,
        "variables": {
            "input": {
                "entityType": "Sample",
                "name": "SAXS Run 1",
                "uri": None,
                "properties": {"beamline": "12.3.1"},
            }
        },
    }


def test_create_link_resolves_tiled_nodes(monkeypatch):
    client = LinksClient("http://example.com")
    subject = Entity(
        id="ent-1",
        entity_type="Experiment",
        name="exp",
        properties=None,
        created_at="2026-01-01T00:00:00Z",
    )

    class DummyNode:
        pass

    node = DummyNode()
    seen: dict[str, object] = {}

    def fake_get_or_create_entity(resolved_client: LinksClient, resolved_node: DummyNode) -> Entity:
        assert resolved_client is client
        assert resolved_node is node
        return Entity(
            id="ent-2",
            entity_type="TiledNode",
            name="node",
            properties={"uri": "http://example/node"},
            created_at="2026-01-01T00:00:00Z",
        )

    def fake_execute(query: str, variables: dict | None = None) -> dict:
        seen["query"] = query
        seen["variables"] = variables
        return {
            "createLink": {
                "id": "lnk-1",
                "subjectId": "ent-1",
                "predicate": "processed_from",
                "objectId": "ent-2",
                "properties": {"confidence": 0.99},
                "createdAt": "2026-01-01T00:00:00Z",
            }
        }

    monkeypatch.setattr(tiled_module, "get_or_create_entity", fake_get_or_create_entity)
    monkeypatch.setattr(client, "_execute", fake_execute)

    link = client.create_link(subject, "processed_from", node, {"confidence": 0.99})

    assert link.id == "lnk-1"
    assert seen["query"] == base_module._CREATE_LINK_MUTATION
    assert seen["variables"] == {
        "input": {
            "subjectId": "ent-1",
            "predicate": "processed_from",
            "objectId": "ent-2",
            "properties": {"confidence": 0.99},
        }
    }


def test_find_links_deduplicates_records(monkeypatch):
    client = LinksClient("http://example.com")
    seen: dict[str, object] = {}

    def fake_execute(query: str, variables: dict | None = None) -> dict:
        seen["query"] = query
        seen["variables"] = variables
        return {
            "asSubject": [
                {
                    "id": "lnk-1",
                    "subjectId": "ent-1",
                    "predicate": "rel",
                    "objectId": "ent-2",
                    "properties": None,
                    "createdAt": "2026-01-01T00:00:00Z",
                }
            ],
            "asObject": [
                {
                    "id": "lnk-1",
                    "subjectId": "ent-1",
                    "predicate": "rel",
                    "objectId": "ent-2",
                    "properties": None,
                    "createdAt": "2026-01-01T00:00:00Z",
                },
                {
                    "id": "lnk-2",
                    "subjectId": "ent-3",
                    "predicate": "rel",
                    "objectId": "ent-1",
                    "properties": {"role": "object"},
                    "createdAt": "2026-01-01T00:00:01Z",
                },
            ],
        }

    monkeypatch.setattr(client, "_execute", fake_execute)

    links = client.find_links("ent-1", predicate="rel", limit=5, offset=2)

    assert [link.id for link in links] == ["lnk-1", "lnk-2"]
    assert seen["query"] == base_module._FIND_LINKS_QUERY
    assert seen["variables"] == {
        "subjectId": "ent-1",
        "objectId": "ent-1",
        "predicate": "rel",
        "limit": 5,
        "offset": 2,
    }


# ---------------------------------------------------------------------------
# Tiled integration helpers
# ---------------------------------------------------------------------------


def test_node_uri_extracts_uri_attribute():
    class Node:
        uri = "https://tiled.example.com/datasets/run1"

    assert _node_uri(Node()) == "https://tiled.example.com/datasets/run1"


def test_node_uri_raises_when_no_uri_attribute():
    with pytest.raises(TypeError, match="Cannot extract a URI"):
        _node_uri(object())


def test_node_name_uses_key_attribute():
    class Node:
        key = "my-run"

    assert _node_name(Node(), "https://example.com/my-run") == "my-run"


def test_node_name_falls_back_to_uri_segment():
    assert _node_name(object(), "https://example.com/some/path/") == "path"


def test_get_or_create_entity_returns_cached():
    client = LinksClient("http://example.com")
    cached = Entity(
        id="ent-cached",
        entity_type="tiled",
        name="cached-node",
        properties=None,
        created_at="2026-01-01T00:00:00Z",
    )
    client._tiled_cache["https://tiled.example.com/node"] = cached

    class Node:
        uri = "https://tiled.example.com/node"

    result = tiled_get_or_create(client, Node())
    assert result.id == "ent-cached"


def test_get_or_create_entity_creates_and_caches(monkeypatch):
    client = LinksClient("http://example.com")

    def fake_execute(query: str, variables: dict | None = None) -> dict:
        return {
            "createEntity": {
                "id": "ent-new",
                "entityType": "tiled",
                "name": "new-node",
                "properties": None,
                "createdAt": "2026-01-01T00:00:00Z",
                "uri": "https://tiled.example.com/new-node",
            }
        }

    monkeypatch.setattr(client, "_execute", fake_execute)

    class Node:
        uri = "https://tiled.example.com/new-node"
        key = "new-node"

    result = tiled_get_or_create(client, Node())
    assert result.id == "ent-new"
    assert "https://tiled.example.com/new-node" in client._tiled_cache
