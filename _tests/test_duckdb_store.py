"""
Module: test_duckdb_store.py
Description: Tests for the DuckDB-backed TripleStore implementation.
"""

import asyncio

import pytest

from splash_links.duckdb_store import DuckDBStore
from splash_links.models import TripleCreate, TripleFilter


@pytest.fixture
def store():
    """Return an initialized in-memory DuckDBStore."""
    s = DuckDBStore(":memory:")
    asyncio.get_event_loop().run_until_complete(s.initialize())
    yield s
    asyncio.get_event_loop().run_until_complete(s.close())


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_add_and_get_triple(store):
    triple_in = TripleCreate(
        subject="http://example.com/A",
        predicate="http://schema.org/knows",
        object="http://example.com/B",
    )
    triple = run(store.add_triple(triple_in))
    assert triple.id is not None
    assert triple.created_at is not None

    fetched = run(store.get_triple(triple.id))
    assert fetched is not None
    assert fetched.subject == "http://example.com/A"
    assert fetched.predicate == "http://schema.org/knows"
    assert fetched.object == "http://example.com/B"


def test_get_triple_not_found(store):
    result = run(store.get_triple("does-not-exist"))
    assert result is None


def test_search_triples_no_filter(store):
    for i in range(3):
        run(
            store.add_triple(
                TripleCreate(
                    subject=f"http://example.com/S{i}",
                    predicate="http://example.com/rel",
                    object=f"http://example.com/O{i}",
                )
            )
        )
    results = run(store.search_triples(TripleFilter()))
    assert len(results) >= 3


def test_search_triples_filter_by_predicate(store):
    run(
        store.add_triple(
            TripleCreate(
                subject="http://example.com/S",
                predicate="http://example.com/unique-pred",
                object="http://example.com/O",
            )
        )
    )
    results = run(
        store.search_triples(TripleFilter(predicate="http://example.com/unique-pred"))
    )
    assert len(results) == 1
    assert results[0].predicate == "http://example.com/unique-pred"


def test_search_triples_filter_by_namespace(store):
    ns = "my-namespace"
    run(
        store.add_triple(
            TripleCreate(
                subject="http://example.com/S",
                predicate="http://example.com/rel",
                object="http://example.com/O",
                namespace=ns,
            )
        )
    )
    results = run(store.search_triples(TripleFilter(namespace=ns)))
    assert len(results) >= 1
    assert all(r.namespace == ns for r in results)


def test_delete_triple(store):
    triple = run(
        store.add_triple(
            TripleCreate(
                subject="http://example.com/Del",
                predicate="http://example.com/rel",
                object="http://example.com/O",
            )
        )
    )
    deleted = run(store.delete_triple(triple.id))
    assert deleted is True

    result = run(store.get_triple(triple.id))
    assert result is None


def test_delete_triple_not_found(store):
    deleted = run(store.delete_triple("nonexistent"))
    assert deleted is False


def test_search_pagination(store):
    # Fresh store; add 5 items with a shared predicate
    pred = "http://example.com/paginate-pred"
    for i in range(5):
        run(
            store.add_triple(
                TripleCreate(
                    subject=f"http://example.com/Pg{i}",
                    predicate=pred,
                    object=f"http://example.com/Obj{i}",
                )
            )
        )
    page1 = run(store.search_triples(TripleFilter(predicate=pred, limit=3, offset=0)))
    page2 = run(store.search_triples(TripleFilter(predicate=pred, limit=3, offset=3)))

    assert len(page1) == 3
    assert len(page2) == 2
    ids1 = {t.id for t in page1}
    ids2 = {t.id for t in page2}
    assert ids1.isdisjoint(ids2)
