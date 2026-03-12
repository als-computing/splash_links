"""
Module: test_api.py
Description: Tests for the splash_links REST API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from splash_links.duckdb_store import DuckDBStore
from splash_links.main import app, get_store


@pytest.fixture(scope="module")
def client():
    """Create an in-memory DuckDB store and wire it into the app for testing."""
    store = DuckDBStore(":memory:")

    import asyncio

    asyncio.get_event_loop().run_until_complete(store.initialize())

    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_create_triple(client):
    response = client.post(
        "/triples",
        json={
            "subject": "http://example.com/Alice",
            "predicate": "http://schema.org/knows",
            "object": "http://example.com/Bob",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["subject"] == "http://example.com/Alice"
    assert data["predicate"] == "http://schema.org/knows"
    assert data["object"] == "http://example.com/Bob"
    assert "id" in data
    assert "created_at" in data


def test_get_triple(client):
    # Create first
    create_resp = client.post(
        "/triples",
        json={
            "subject": "http://example.com/Cat",
            "predicate": "http://schema.org/name",
            "object": "Whiskers",
        },
    )
    triple_id = create_resp.json()["id"]

    # Retrieve by ID
    get_resp = client.get(f"/triples/{triple_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == triple_id
    assert data["object"] == "Whiskers"


def test_get_triple_not_found(client):
    response = client.get("/triples/nonexistent-id")
    assert response.status_code == 404


def test_list_triples(client):
    # Ensure at least one triple exists
    client.post(
        "/triples",
        json={
            "subject": "http://example.com/X",
            "predicate": "http://example.com/rel",
            "object": "http://example.com/Y",
            "namespace": "test-ns",
        },
    )
    response = client.get("/triples")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


def test_list_triples_filter_by_subject(client):
    unique_subject = "http://example.com/UniqueSubject123"
    client.post(
        "/triples",
        json={
            "subject": unique_subject,
            "predicate": "http://example.com/rel",
            "object": "http://example.com/Obj",
        },
    )
    response = client.get(f"/triples?subject={unique_subject}")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["subject"] == unique_subject


def test_list_triples_filter_by_namespace(client):
    ns = "filter-test-namespace"
    client.post(
        "/triples",
        json={
            "subject": "http://example.com/A",
            "predicate": "http://example.com/rel",
            "object": "http://example.com/B",
            "namespace": ns,
        },
    )
    response = client.get(f"/triples?namespace={ns}")
    assert response.status_code == 200
    results = response.json()
    assert all(r["namespace"] == ns for r in results)
    assert len(results) >= 1


def test_delete_triple(client):
    create_resp = client.post(
        "/triples",
        json={
            "subject": "http://example.com/ToDelete",
            "predicate": "http://example.com/rel",
            "object": "http://example.com/Obj",
        },
    )
    triple_id = create_resp.json()["id"]

    del_resp = client.delete(f"/triples/{triple_id}")
    assert del_resp.status_code == 204

    # Should be gone now
    get_resp = client.get(f"/triples/{triple_id}")
    assert get_resp.status_code == 404


def test_delete_triple_not_found(client):
    response = client.delete("/triples/nonexistent-id")
    assert response.status_code == 404
