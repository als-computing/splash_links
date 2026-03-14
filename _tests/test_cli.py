"""Tests for the server-side CLI (splash_links.cli)."""

from __future__ import annotations

from datetime import datetime, timezone

from typer.testing import CliRunner

import splash_links.cli as cli_module
from splash_links.cli import app
from splash_links.store import EntityRecord, LinkRecord

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entity(**kw) -> EntityRecord:
    defaults = dict(
        id="ent-1",
        entity_type="Dataset",
        name="test",
        uri=None,
        properties={},
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kw)
    return EntityRecord(**defaults)


def _make_link(**kw) -> LinkRecord:
    defaults = dict(
        id="lnk-1",
        subject_id="ent-1",
        predicate="produced",
        object_id="ent-2",
        properties={},
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kw)
    return LinkRecord(**defaults)


class FakeStore:
    def __init__(self, entities=None, links=None):
        self._entities = entities or []
        self._links = links or []

    def list_entities(self, entity_type=None, limit=50, offset=0):
        if entity_type:
            return [e for e in self._entities if e.entity_type == entity_type]
        return self._entities

    def find_links(self, subject_id=None, predicate=None, object_id=None, limit=50, offset=0):
        return self._links

    def close(self):
        pass


# ---------------------------------------------------------------------------
# entities command
# ---------------------------------------------------------------------------


def test_entities_shows_rows(monkeypatch):
    fake = FakeStore(entities=[_make_entity(name="run-001")])
    monkeypatch.setattr(cli_module, "_open_store", lambda: fake)
    result = runner.invoke(app, ["entities"])
    assert result.exit_code == 0
    assert "run-001" in result.output


def test_entities_no_rows_prints_message(monkeypatch):
    monkeypatch.setattr(cli_module, "_open_store", lambda: FakeStore())
    result = runner.invoke(app, ["entities"])
    assert result.exit_code == 0
    assert "No entities found" in result.output


def test_entities_type_filter(monkeypatch):
    fake = FakeStore(entities=[_make_entity(entity_type="Sample", name="s1")])
    monkeypatch.setattr(cli_module, "_open_store", lambda: fake)
    result = runner.invoke(app, ["entities", "--type", "Sample"])
    assert result.exit_code == 0
    assert "s1" in result.output


# ---------------------------------------------------------------------------
# links command
# ---------------------------------------------------------------------------


def test_links_shows_rows(monkeypatch):
    fake = FakeStore(links=[_make_link(predicate="produced")])
    monkeypatch.setattr(cli_module, "_open_store", lambda: fake)
    result = runner.invoke(app, ["links"])
    assert result.exit_code == 0
    assert "produced" in result.output


def test_links_no_rows_prints_message(monkeypatch):
    monkeypatch.setattr(cli_module, "_open_store", lambda: FakeStore())
    result = runner.invoke(app, ["links"])
    assert result.exit_code == 0
    assert "No links found" in result.output


def test_links_filter_options(monkeypatch):
    fake = FakeStore(links=[_make_link()])
    monkeypatch.setattr(cli_module, "_open_store", lambda: fake)
    result = runner.invoke(app, ["links", "--subject", "ent-1", "--predicate", "produced"])
    assert result.exit_code == 0


def test_links_with_properties(monkeypatch):
    fake = FakeStore(links=[_make_link(properties={"confidence": 0.99})])
    monkeypatch.setattr(cli_module, "_open_store", lambda: fake)
    result = runner.invoke(app, ["links"])
    assert result.exit_code == 0
    assert "confidence" in result.output


# ---------------------------------------------------------------------------
# _open_store — missing DB
# ---------------------------------------------------------------------------


def test_open_store_missing_db(monkeypatch, tmp_path):
    missing = str(tmp_path / "nope.sqlite")
    monkeypatch.setenv("SPLASH_LINKS_DB", missing)
    result = runner.invoke(app, ["entities"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main(monkeypatch):
    called = []
    monkeypatch.setattr(cli_module, "app", lambda: called.append(True))
    cli_module.main()
    assert called == [True]
