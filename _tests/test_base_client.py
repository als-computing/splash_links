from __future__ import annotations

import pytest

from splash_links.client import base as base_module
from splash_links.client import tiled as tiled_module
from splash_links.client.base import Entity, LinksClient, from_uri
from splash_links.client.tiled import TiledEntity, _node_name, _node_properties, _node_uri, from_entity
from splash_links.client.tiled import get_or_create_entity as tiled_get_or_create


class FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_from_uri_supports_expected_schemes():
    assert from_uri("splash://localhost:8080")._gql_url == "http://localhost:8080/splash_links/graphql"
    assert from_uri("http://example.com")._gql_url == "http://example.com/splash_links/graphql"
    assert from_uri("https://example.com")._gql_url == "https://example.com/splash_links/graphql"

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
    assert seen["url"] == "http://api:8080/splash_links/graphql"
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


# ---------------------------------------------------------------------------
# _node_properties
# ---------------------------------------------------------------------------


def test_node_properties_captures_specs_and_structure_family():
    class Spec:
        name = "XDI"

    class Node:
        uri = "http://tiled.example.com/api/v1/metadata/exp/run42"
        specs = [Spec()]
        item = {"attributes": {"structure_family": "array"}}

    props = _node_properties(Node())
    assert props["specs"] == ["XDI"]
    assert props["structure_family"] == "array"


def test_node_properties_tolerates_missing_optional_attrs():
    class Node:
        # no specs, no item
        pass

    props = _node_properties(Node())
    assert "specs" not in props
    assert "structure_family" not in props


def test_get_or_create_entity_passes_tiled_properties(monkeypatch):
    client = LinksClient("http://example.com")
    captured: dict = {}

    def fake_execute(query: str, variables: dict | None = None) -> dict:
        captured["variables"] = variables
        return {
            "createEntity": {
                "id": "ent-new",
                "entityType": "tiled",
                "name": "run42",
                "properties": variables["input"]["properties"],
                "createdAt": "2026-01-01T00:00:00Z",
                "uri": "http://tiled.example.com/api/v1/metadata/exp/run42",
            }
        }

    monkeypatch.setattr(client, "_execute", fake_execute)

    class Spec:
        name = "XDI"

    class Node:
        uri = "http://tiled.example.com/api/v1/metadata/exp/run42"
        key = "run42"
        specs = [Spec()]
        item = {"attributes": {"structure_family": "array"}}

    result = tiled_get_or_create(client, Node())
    assert result.id == "ent-new"
    props = captured["variables"]["input"]["properties"]
    assert props["specs"] == ["XDI"]
    assert props["structure_family"] == "array"


# ---------------------------------------------------------------------------
# from_entity
# ---------------------------------------------------------------------------


def test_from_entity_uses_entity_uri(monkeypatch):
    import sys
    import types

    connected_uri: list = []

    class FakeNode:
        pass

    root_node = FakeNode()
    fake_tiled_client = types.ModuleType("tiled.client")
    fake_tiled_client.from_uri = lambda url: (connected_uri.append(url), root_node)[1]
    fake_tiled = types.ModuleType("tiled")
    fake_tiled.client = fake_tiled_client
    monkeypatch.setitem(sys.modules, "tiled", fake_tiled)
    monkeypatch.setitem(sys.modules, "tiled.client", fake_tiled_client)

    entity = Entity(
        id="ent-1",
        entity_type="tiled",
        name="run42",
        uri="http://tiled.example.com/api/v1/metadata/exp/run42",
        properties={},  # no tiled_server_url
        created_at="2026-01-01T00:00:00Z",
    )

    result = from_entity(entity)
    assert result is root_node
    assert connected_uri == ["http://tiled.example.com/api/v1/metadata/exp/run42"]


def test_from_entity_raises_when_no_uri_or_server_url(monkeypatch):
    import sys
    import types

    fake_tiled_client = types.ModuleType("tiled.client")
    fake_tiled_client.from_uri = lambda url: None  # won't be reached
    fake_tiled = types.ModuleType("tiled")
    fake_tiled.client = fake_tiled_client
    monkeypatch.setitem(sys.modules, "tiled", fake_tiled)
    monkeypatch.setitem(sys.modules, "tiled.client", fake_tiled_client)

    entity = Entity(
        id="ent-orphan",
        entity_type="tiled",
        name="orphan",
        uri=None,
        properties={},
        created_at="2026-01-01T00:00:00Z",
    )

    with pytest.raises(ValueError, match="cannot reconnect"):
        from_entity(entity)


# ---------------------------------------------------------------------------
# TiledEntity dispatcher
# ---------------------------------------------------------------------------


def test_entity_from_dict_returns_tiled_entity_for_tiled_type():
    d = {
        "id": "ent-1",
        "entityType": "tiled",
        "name": "run42",
        "uri": "http://tiled.example.com/api/v1/metadata/exp/run42",
        "properties": {"tiled_server_url": "http://tiled.example.com", "tiled_path": ["exp", "run42"]},
        "createdAt": "2026-01-01T00:00:00Z",
    }
    from splash_links.client.base import _entity_from_dict

    result = _entity_from_dict(d)
    assert isinstance(result, TiledEntity)
    assert result.id == "ent-1"


def test_entity_from_dict_returns_plain_entity_for_other_types():
    d = {
        "id": "ent-2",
        "entityType": "Sample",
        "name": "my sample",
        "uri": None,
        "properties": None,
        "createdAt": "2026-01-01T00:00:00Z",
    }
    from splash_links.client.base import _entity_from_dict

    result = _entity_from_dict(d)
    assert type(result) is Entity
    assert result.id == "ent-2"


def test_get_or_create_entity_returns_tiled_entity(monkeypatch):
    """create_entity goes through _entity_from_dict, so tiled entities come back as TiledEntity."""
    client = LinksClient("http://example.com")

    def fake_execute(query: str, variables: dict | None = None) -> dict:
        return {
            "createEntity": {
                "id": "ent-new",
                "entityType": "tiled",
                "name": "run42",
                "uri": "http://tiled.example.com/api/v1/metadata/exp/run42",
                "properties": {"tiled_server_url": "http://tiled.example.com", "tiled_path": ["exp", "run42"]},
                "createdAt": "2026-01-01T00:00:00Z",
            }
        }

    monkeypatch.setattr(client, "_execute", fake_execute)

    class Node:
        uri = "http://tiled.example.com/api/v1/metadata/exp/run42"
        key = "run42"
        specs = []

    result = tiled_get_or_create(client, Node())
    assert isinstance(result, TiledEntity)


def test_tiled_entity_node_calls_from_entity(monkeypatch):
    import sys
    import types

    fake_node = object()
    fake_tiled_client = types.ModuleType("tiled.client")
    fake_tiled_client.from_uri = lambda url: fake_node
    fake_tiled = types.ModuleType("tiled")
    fake_tiled.client = fake_tiled_client
    monkeypatch.setitem(sys.modules, "tiled", fake_tiled)
    monkeypatch.setitem(sys.modules, "tiled.client", fake_tiled_client)

    entity = TiledEntity(
        id="ent-1",
        entity_type="tiled",
        name="run42",
        uri="http://tiled.example.com/api/v1/metadata/exp/run42",
        properties={"tiled_server_url": "http://tiled.example.com", "tiled_path": []},
        created_at="2026-01-01T00:00:00Z",
    )
    assert entity.node() is fake_node
