"""Typer CLI for interacting with the splash-links GraphQL client."""

from __future__ import annotations

import json
from typing import Any, Optional

import typer

from .base import Entity, Link, from_uri

app = typer.Typer(help="Interact with a splash-links GraphQL service.")


def _parse_json_option(name: str, raw: Optional[str]) -> Optional[dict[str, Any]]:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        typer.echo(f"Invalid JSON passed to --{name}: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    if value is None:
        return None
    if not isinstance(value, dict):
        typer.echo(f"--{name} must decode to a JSON object.", err=True)
        raise typer.Exit(code=2)
    return value


def _entity_as_dict(entity: Entity) -> dict[str, Any]:
    return {
        "id": entity.id,
        "entity_type": entity.entity_type,
        "name": entity.name,
        "properties": entity.properties,
        "created_at": entity.created_at,
    }


def _link_as_dict(link: Link) -> dict[str, Any]:
    return {
        "id": link.id,
        "subject_id": link.subject_id,
        "predicate": link.predicate,
        "object_id": link.object_id,
        "properties": link.properties,
        "created_at": link.created_at,
    }


def _emit_json(payload: Any) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@app.command("create-entity")
def create_entity(
    entity_type: str = typer.Option(..., "--entity-type", "-t", help="Entity type label."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Entity display name."),
    properties: Optional[str] = typer.Option(
        None,
        "--properties",
        "-p",
        help='JSON object of properties. Example: {"beamline": "12.3.1"}',
    ),
    uri: str = typer.Option(
        "splash://localhost:8080",
        "--uri",
        "-u",
        envvar="SPLASH_LINKS_URI",
        help="Service URI. Supports splash://, http://, or https://.",
    ),
) -> None:
    """Create an entity through the GraphQL service."""
    props = _parse_json_option("properties", properties)
    client = from_uri(uri)
    try:
        entity = client.create_entity(entity_type=entity_type, properties=props, name=name)
    except Exception as exc:
        typer.echo(f"Failed to create entity: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    _emit_json(_entity_as_dict(entity))


@app.command("create-link")
def create_link(
    subject_id: str = typer.Argument(..., help="Subject entity ID."),
    predicate: str = typer.Argument(..., help="Relationship predicate."),
    object_id: str = typer.Argument(..., help="Object entity ID."),
    properties: Optional[str] = typer.Option(
        None,
        "--properties",
        "-p",
        help='JSON object of properties. Example: {"confidence": 0.98}',
    ),
    uri: str = typer.Option(
        "splash://localhost:8080",
        "--uri",
        "-u",
        envvar="SPLASH_LINKS_URI",
        help="Service URI. Supports splash://, http://, or https://.",
    ),
) -> None:
    """Create a link between two entity IDs."""
    props = _parse_json_option("properties", properties)
    client = from_uri(uri)
    try:
        link = client.create_link(subject_id=subject_id, predicate=predicate, object_id=object_id, properties=props)
    except Exception as exc:
        typer.echo(f"Failed to create link: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    _emit_json(_link_as_dict(link))


@app.command("find-links")
def find_links(
    entity_id: str = typer.Argument(..., help="Entity ID to match as subject or object."),
    predicate: Optional[str] = typer.Option(None, "--predicate", "-p", help="Optional predicate filter."),
    limit: int = typer.Option(100, "--limit", "-n", help="Maximum number of links to fetch."),
    offset: int = typer.Option(0, "--offset", "-o", help="Pagination offset."),
    uri: str = typer.Option(
        "splash://localhost:8080",
        "--uri",
        "-u",
        envvar="SPLASH_LINKS_URI",
        help="Service URI. Supports splash://, http://, or https://.",
    ),
) -> None:
    """Find links where an entity participates as subject or object."""
    client = from_uri(uri)
    try:
        links = client.find_links(entity=entity_id, predicate=predicate, limit=limit, offset=offset)
    except Exception as exc:
        typer.echo(f"Failed to find links: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    _emit_json([_link_as_dict(link) for link in links])


def main() -> None:
    app()
