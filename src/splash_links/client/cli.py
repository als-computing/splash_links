"""Typer CLI for interacting with the splash-links GraphQL client."""

from __future__ import annotations

import json
from typing import Any, Optional

import typer

from .base import Embedding, EmbeddingMatch, Entity, Link, from_uri

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
    return entity.model_dump()


def _link_as_dict(link: Link) -> dict[str, Any]:
    return link.model_dump()


def _embedding_as_dict(embedding: Embedding) -> dict[str, Any]:
    return embedding.model_dump()


def _embedding_match_as_dict(match: EmbeddingMatch) -> dict[str, Any]:
    payload = match.model_dump()
    payload["embedding"] = _embedding_as_dict(match.embedding)
    return payload


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
        link = client.create_link(
            subject_id=subject_id,
            predicate=predicate,
            object_id=object_id,
            properties=props,
        )
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


@app.command("create-embedding")
def create_embedding(
    entity_id: str = typer.Argument(..., help="Entity ID that owns the embedding."),
    vector: str = typer.Option(..., "--vector", "-v", help="JSON array of numeric embedding values."),
    embedding_model: str = typer.Option("default", "--model", "-m", help="Embedding model label."),
    properties: Optional[str] = typer.Option(
        None,
        "--properties",
        "-p",
        help='JSON object of metadata. Example: {"chunk": 3}',
    ),
    uri: str = typer.Option(
        "splash://localhost:8080",
        "--uri",
        "-u",
        envvar="SPLASH_LINKS_URI",
        help="Service URI. Supports splash://, http://, or https://.",
    ),
) -> None:
    """Create an embedding for an entity."""
    props = _parse_json_option("properties", properties)
    try:
        raw_vector = json.loads(vector)
    except json.JSONDecodeError as exc:
        typer.echo(f"Invalid JSON passed to --vector: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    if not isinstance(raw_vector, list):
        typer.echo("--vector must decode to a JSON array.", err=True)
        raise typer.Exit(code=2)

    client = from_uri(uri)
    try:
        embedding = client.create_embedding(
            entity_id=entity_id,
            vector=raw_vector,
            embedding_model=embedding_model,
            properties=props,
        )
    except Exception as exc:
        typer.echo(f"Failed to create embedding: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    _emit_json(_embedding_as_dict(embedding))


@app.command("nearest-embeddings")
def nearest_embeddings(
    vector: str = typer.Option(..., "--vector", "-v", help="JSON array of numeric query values."),
    embedding_model: Optional[str] = typer.Option(None, "--model", "-m", help="Optional embedding model filter."),
    entity_id: Optional[str] = typer.Option(None, "--entity-id", "-e", help="Optional entity filter."),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum number of matches to fetch."),
    offset: int = typer.Option(0, "--offset", "-o", help="Pagination offset."),
    uri: str = typer.Option(
        "splash://localhost:8080",
        "--uri",
        "-u",
        envvar="SPLASH_LINKS_URI",
        help="Service URI. Supports splash://, http://, or https://.",
    ),
) -> None:
    """Find embeddings nearest to a query vector."""
    try:
        raw_vector = json.loads(vector)
    except json.JSONDecodeError as exc:
        typer.echo(f"Invalid JSON passed to --vector: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    if not isinstance(raw_vector, list):
        typer.echo("--vector must decode to a JSON array.", err=True)
        raise typer.Exit(code=2)

    client = from_uri(uri)
    try:
        matches = client.find_nearest_embeddings(
            vector=raw_vector,
            embedding_model=embedding_model,
            entity_id=entity_id,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        typer.echo(f"Failed to search embeddings: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    _emit_json([_embedding_match_as_dict(match) for match in matches])


def main() -> None:
    app()
