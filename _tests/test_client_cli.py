from __future__ import annotations

import json

from typer.testing import CliRunner

from splash_links import cli as root_cli
from splash_links.client import cli as client_cli
from splash_links.client.base import Entity, Link

runner = CliRunner()


def test_create_entity_command_outputs_json(monkeypatch):
    seen: dict[str, object] = {}

    class FakeClient:
        def create_entity(self, entity_type, properties=None, name=None):
            seen["entity_type"] = entity_type
            seen["properties"] = properties
            seen["name"] = name
            return Entity(
                id="ent-1",
                entity_type=entity_type,
                name=name or entity_type,
                properties=properties,
                created_at="2026-01-01T00:00:00Z",
            )

    def fake_from_uri(uri: str):
        seen["uri"] = uri
        return FakeClient()

    monkeypatch.setattr(client_cli, "from_uri", fake_from_uri)

    result = runner.invoke(
        client_cli.app,
        [
            "create-entity",
            "--uri",
            "splash://api:8080",
            "--entity-type",
            "Experiment",
            "--name",
            "SAXS run 42",
            "--properties",
            '{"beamline":"12.3.1"}',
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["id"] == "ent-1"
    assert payload["entity_type"] == "Experiment"
    assert seen == {
        "uri": "splash://api:8080",
        "entity_type": "Experiment",
        "properties": {"beamline": "12.3.1"},
        "name": "SAXS run 42",
    }


def test_create_entity_invalid_json_exits_2():
    result = runner.invoke(
        client_cli.app,
        ["create-entity", "--entity-type", "Experiment", "--properties", "not-json"],
    )
    assert result.exit_code == 2
    assert "Invalid JSON passed to --properties" in result.output


def test_find_links_command_outputs_list(monkeypatch):
    seen: dict[str, object] = {}

    class FakeClient:
        def find_links(self, entity, predicate=None, limit=100, offset=0):
            seen["entity"] = entity
            seen["predicate"] = predicate
            seen["limit"] = limit
            seen["offset"] = offset
            return [
                Link(
                    id="lnk-1",
                    subject_id="ent-1",
                    predicate="processed_from",
                    object_id="ent-2",
                    properties={"confidence": 0.99},
                    created_at="2026-01-01T00:00:00Z",
                )
            ]

    monkeypatch.setattr(client_cli, "from_uri", lambda uri: FakeClient())

    result = runner.invoke(
        client_cli.app,
        ["find-links", "ent-1", "--predicate", "processed_from", "--limit", "20", "--offset", "1"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert payload[0]["id"] == "lnk-1"
    assert seen == {
        "entity": "ent-1",
        "predicate": "processed_from",
        "limit": 20,
        "offset": 1,
    }


def test_root_cli_exposes_client_subcommands(monkeypatch):
    class FakeClient:
        def find_links(self, entity, predicate=None, limit=100, offset=0):
            return [
                Link(
                    id="lnk-1",
                    subject_id=entity,
                    predicate=predicate or "related_to",
                    object_id="ent-2",
                    properties=None,
                    created_at="2026-01-01T00:00:00Z",
                )
            ]

    monkeypatch.setattr(client_cli, "from_uri", lambda uri: FakeClient())

    result = runner.invoke(root_cli.app, ["client", "find-links", "ent-1"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload[0]["subject_id"] == "ent-1"
