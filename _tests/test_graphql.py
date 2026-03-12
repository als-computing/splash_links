"""
Module: test_graphql.py
Description: Tests for the GraphQL endpoint of the splash_links service.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from splash_links.duckdb_store import DuckDBStore
from splash_links.main import app, get_store


@pytest.fixture(scope="module")
def client():
    store = DuckDBStore(":memory:")
    asyncio.get_event_loop().run_until_complete(store.initialize())
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as c:
        yield c, store
    app.dependency_overrides.clear()


def gql(client, query: str, variables: dict = None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = client.post("/graphql", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_graphql_add_triple(client):
    c, _ = client
    result = gql(
        c,
        """
        mutation {
            addTriple(
                subject: "http://example.com/Alice",
                predicate: "http://schema.org/knows",
                object: "http://example.com/Bob"
            ) {
                id
                subject
                predicate
                object
                namespace
                createdAt
            }
        }
        """,
    )
    data = result["data"]["addTriple"]
    assert data["subject"] == "http://example.com/Alice"
    assert data["predicate"] == "http://schema.org/knows"
    assert data["object"] == "http://example.com/Bob"
    assert data["id"] is not None


def test_graphql_query_triple(client):
    c, _ = client
    # First create one
    add_result = gql(
        c,
        """
        mutation {
            addTriple(
                subject: "http://example.com/Cat",
                predicate: "http://schema.org/name",
                object: "Whiskers"
            ) { id }
        }
        """,
    )
    triple_id = add_result["data"]["addTriple"]["id"]

    query_result = gql(
        c,
        """
        query($id: String!) {
            triple(id: $id) {
                id
                subject
                object
            }
        }
        """,
        {"id": triple_id},
    )
    triple = query_result["data"]["triple"]
    assert triple["id"] == triple_id
    assert triple["object"] == "Whiskers"


def test_graphql_query_triples_with_filter(client):
    c, _ = client
    unique_pred = "http://example.com/gql-unique-pred"
    gql(
        c,
        f"""
        mutation {{
            addTriple(
                subject: "http://example.com/S",
                predicate: "{unique_pred}",
                object: "http://example.com/O"
            ) {{ id }}
        }}
        """,
    )
    result = gql(
        c,
        """
        query($pred: String!) {
            triples(predicate: $pred) {
                id
                predicate
            }
        }
        """,
        {"pred": unique_pred},
    )
    triples = result["data"]["triples"]
    assert len(triples) == 1
    assert triples[0]["predicate"] == unique_pred


def test_graphql_delete_triple(client):
    c, _ = client
    add_result = gql(
        c,
        """
        mutation {
            addTriple(
                subject: "http://example.com/ToDelete",
                predicate: "http://example.com/rel",
                object: "http://example.com/Obj"
            ) { id }
        }
        """,
    )
    triple_id = add_result["data"]["addTriple"]["id"]

    del_result = gql(
        c,
        """
        mutation($id: String!) {
            deleteTriple(id: $id)
        }
        """,
        {"id": triple_id},
    )
    assert del_result["data"]["deleteTriple"] is True

    # Should no longer be found
    get_result = gql(
        c,
        """
        query($id: String!) {
            triple(id: $id)  { id }
        }
        """,
        {"id": triple_id},
    )
    assert get_result["data"]["triple"] is None


def test_graphql_triple_not_found(client):
    c, _ = client
    result = gql(
        c,
        """
        query {
            triple(id: "does-not-exist") { id }
        }
        """,
    )
    assert result["data"]["triple"] is None
