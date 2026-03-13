"""
Integration tests for the splash-links service.

All tests use an in-memory DuckDB store and the ASGI test client so no
external process or file is needed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from splash_links.app import create_app
from splash_links.store import DuckDBStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store():
    """Fresh in-memory store for each test."""
    s = DuckDBStore(":memory:")
    yield s
    s.close()


@pytest.fixture()
def client():
    """ASGI test client backed by an in-memory store."""
    app = create_app(db_path=":memory:")
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GQL = "/graphql"


def gql(client: TestClient, query: str, variables: dict | None = None) -> dict:
    resp = client.post(_GQL, json={"query": query, "variables": variables or {}})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "errors" not in body, body.get("errors")
    return body["data"]


CREATE_ENTITY = """
mutation CreateEntity($input: CreateEntityInput!) {
  createEntity(input: $input) {
    id
    entityType
    name
    properties
    createdAt
  }
}
"""

CREATE_LINK = """
mutation CreateLink($input: CreateLinkInput!) {
  createLink(input: $input) {
    id
    subjectId
    predicate
    objectId
    properties
    createdAt
    subject { id name }
    object  { id name }
  }
}
"""


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Store unit tests (no HTTP)
# ---------------------------------------------------------------------------


class TestDuckDBStore:
    def test_create_and_get_entity(self, store):
        e = store.create_entity("Dataset", "SAXS run 001", {"beamline": "12.3.1"})
        assert e.id
        assert e.entity_type == "Dataset"
        assert e.name == "SAXS run 001"
        assert e.properties == {"beamline": "12.3.1"}

        fetched = store.get_entity(e.id)
        assert fetched is not None
        assert fetched.id == e.id

    def test_get_entity_missing(self, store):
        assert store.get_entity("does-not-exist") is None

    def test_list_entities_all(self, store):
        store.create_entity("Dataset", "A")
        store.create_entity("Experiment", "B")
        all_entities = store.list_entities()
        assert len(all_entities) == 2

    def test_list_entities_filtered(self, store):
        store.create_entity("Dataset", "A")
        store.create_entity("Experiment", "B")
        datasets = store.list_entities(entity_type="Dataset")
        assert len(datasets) == 1
        assert datasets[0].name == "A"

    def test_delete_entity_cascades_links(self, store):
        e1 = store.create_entity("Experiment", "exp-1")
        e2 = store.create_entity("Dataset", "ds-1")
        lnk = store.create_link(e1.id, "produced", e2.id)

        assert store.delete_entity(e1.id) is True
        assert store.get_entity(e1.id) is None
        assert store.get_link(lnk.id) is None  # cascade deleted

    def test_delete_entity_not_found(self, store):
        assert store.delete_entity("ghost") is False

    def test_create_link(self, store):
        e1 = store.create_entity("Experiment", "exp-1")
        e2 = store.create_entity("Dataset", "ds-1")
        lnk = store.create_link(e1.id, "produced", e2.id, {"confidence": 0.99})

        assert lnk.subject_id == e1.id
        assert lnk.predicate == "produced"
        assert lnk.object_id == e2.id
        assert lnk.properties == {"confidence": 0.99}

    def test_create_link_missing_subject_raises(self, store):
        e2 = store.create_entity("Dataset", "ds-1")
        with pytest.raises(ValueError, match="Subject"):
            store.create_link("bad-id", "produced", e2.id)

    def test_create_link_missing_object_raises(self, store):
        e1 = store.create_entity("Experiment", "exp-1")
        with pytest.raises(ValueError, match="Object"):
            store.create_link(e1.id, "produced", "bad-id")

    def test_find_links_by_subject(self, store):
        e1 = store.create_entity("A", "a")
        e2 = store.create_entity("B", "b")
        e3 = store.create_entity("C", "c")
        store.create_link(e1.id, "rel", e2.id)
        store.create_link(e1.id, "rel", e3.id)
        store.create_link(e2.id, "rel", e3.id)

        links = store.find_links(subject_id=e1.id)
        assert len(links) == 2

    def test_find_links_by_predicate(self, store):
        e1 = store.create_entity("A", "a")
        e2 = store.create_entity("B", "b")
        store.create_link(e1.id, "produced", e2.id)
        store.create_link(e1.id, "consumed", e2.id)

        produced = store.find_links(predicate="produced")
        assert len(produced) == 1

    def test_delete_link(self, store):
        e1 = store.create_entity("A", "a")
        e2 = store.create_entity("B", "b")
        lnk = store.create_link(e1.id, "rel", e2.id)

        assert store.delete_link(lnk.id) is True
        assert store.get_link(lnk.id) is None
        assert store.delete_link(lnk.id) is False  # already gone


# ---------------------------------------------------------------------------
# GraphQL integration tests (via HTTP)
# ---------------------------------------------------------------------------


class TestGraphQL:
    def test_create_entity(self, client):
        data = gql(
            client,
            CREATE_ENTITY,
            {"input": {"entityType": "Dataset", "name": "run-001", "properties": {"energy": 7.0}}},
        )
        e = data["createEntity"]
        assert e["name"] == "run-001"
        assert e["entityType"] == "Dataset"
        assert e["properties"] == {"energy": 7.0}

    def test_query_entity(self, client):
        created = gql(
            client,
            CREATE_ENTITY,
            {"input": {"entityType": "Experiment", "name": "exp-42"}},
        )["createEntity"]

        fetched = gql(
            client,
            "query Q($id: ID!) { entity(id: $id) { id name entityType } }",
            {"id": created["id"]},
        )["entity"]
        assert fetched["id"] == created["id"]
        assert fetched["name"] == "exp-42"

    def test_query_entity_not_found(self, client):
        result = gql(
            client,
            "{ entity(id: \"00000000-0000-0000-0000-000000000000\") { id } }",
        )
        assert result["entity"] is None

    def test_list_entities(self, client):
        for i in range(3):
            gql(client, CREATE_ENTITY, {"input": {"entityType": "Sample", "name": f"s-{i}"}})

        data = gql(client, "{ entities(entityType: \"Sample\") { id name } }")
        assert len(data["entities"]) == 3

    def test_create_and_traverse_link(self, client):
        exp = gql(client, CREATE_ENTITY, {"input": {"entityType": "Experiment", "name": "exp"}})["createEntity"]
        ds = gql(client, CREATE_ENTITY, {"input": {"entityType": "Dataset", "name": "ds"}})["createEntity"]

        link_data = gql(
            client,
            CREATE_LINK,
            {"input": {"subjectId": exp["id"], "predicate": "produced", "objectId": ds["id"]}},
        )["createLink"]
        assert link_data["predicate"] == "produced"
        assert link_data["subject"]["name"] == "exp"
        assert link_data["object"]["name"] == "ds"

    def test_traverse_outgoing_and_incoming(self, client):
        exp = gql(client, CREATE_ENTITY, {"input": {"entityType": "Experiment", "name": "exp"}})["createEntity"]
        ds = gql(client, CREATE_ENTITY, {"input": {"entityType": "Dataset", "name": "ds"}})["createEntity"]
        gql(
            client,
            CREATE_LINK,
            {"input": {"subjectId": exp["id"], "predicate": "produced", "objectId": ds["id"]}},
        )

        out = gql(
            client,
            "query Q($id: ID!) { entity(id: $id) { outgoingLinks { predicate object { name } } } }",
            {"id": exp["id"]},
        )["entity"]["outgoingLinks"]
        assert out[0]["predicate"] == "produced"
        assert out[0]["object"]["name"] == "ds"

        inc = gql(
            client,
            "query Q($id: ID!) { entity(id: $id) { incomingLinks { predicate subject { name } } } }",
            {"id": ds["id"]},
        )["entity"]["incomingLinks"]
        assert inc[0]["subject"]["name"] == "exp"

    def test_filter_links(self, client):
        e1 = gql(client, CREATE_ENTITY, {"input": {"entityType": "A", "name": "a"}})["createEntity"]
        e2 = gql(client, CREATE_ENTITY, {"input": {"entityType": "B", "name": "b"}})["createEntity"]
        gql(client, CREATE_LINK, {"input": {"subjectId": e1["id"], "predicate": "likes", "objectId": e2["id"]}})
        gql(client, CREATE_LINK, {"input": {"subjectId": e1["id"], "predicate": "hates", "objectId": e2["id"]}})

        likes = gql(client, "{ links(predicate: \"likes\") { id predicate } }")["links"]
        assert len(likes) == 1
        assert likes[0]["predicate"] == "likes"

    def test_delete_entity_cascades(self, client):
        e1 = gql(client, CREATE_ENTITY, {"input": {"entityType": "A", "name": "a"}})["createEntity"]
        e2 = gql(client, CREATE_ENTITY, {"input": {"entityType": "B", "name": "b"}})["createEntity"]
        lnk = gql(
            client,
            CREATE_LINK,
            {"input": {"subjectId": e1["id"], "predicate": "rel", "objectId": e2["id"]}},
        )["createLink"]

        deleted = gql(client, "mutation D($id: ID!) { deleteEntity(id: $id) }", {"id": e1["id"]})
        assert deleted["deleteEntity"] is True

        gone = gql(client, "query Q($id: ID!) { link(id: $id) { id } }", {"id": lnk["id"]})
        assert gone["link"] is None

    def test_delete_link(self, client):
        e1 = gql(client, CREATE_ENTITY, {"input": {"entityType": "A", "name": "a"}})["createEntity"]
        e2 = gql(client, CREATE_ENTITY, {"input": {"entityType": "B", "name": "b"}})["createEntity"]
        lnk = gql(
            client,
            CREATE_LINK,
            {"input": {"subjectId": e1["id"], "predicate": "rel", "objectId": e2["id"]}},
        )["createLink"]

        result = gql(client, "mutation D($id: ID!) { deleteLink(id: $id) }", {"id": lnk["id"]})
        assert result["deleteLink"] is True

        # Entities still exist
        still_there = gql(client, "query Q($id: ID!) { entity(id: $id) { id } }", {"id": e1["id"]})
        assert still_there["entity"] is not None
