"""
CLI for splash-links local DB inspection and remote client operations.

Usage:
    splash-links entities [--type TYPE] [--limit N]
    splash-links links    [--subject ID] [--predicate PRED] [--object ID] [--limit N]
    splash-links shell    # drop into the raw SQLite CLI
    splash-links client --help

The database file is read from the SPLASH_LINKS_DB environment variable,
defaulting to links.sqlite in the current directory.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from .client.cli import app as client_app
from .store import SQLiteStore

app = typer.Typer(help="Splash-links command line tools.")
app.add_typer(client_app, name="client", help="Interact with the GraphQL service via the HTTP client.")
console = Console(width=120)


def _db_path() -> str:
    return os.environ.get("SPLASH_LINKS_DB", "links.sqlite")


def _open_store() -> SQLiteStore:
    path = _db_path()
    if path != ":memory:" and not os.path.exists(path):
        typer.echo(f"Database not found: {path}", err=True)
        raise typer.Exit(code=1)
    return SQLiteStore(path)


@app.command()
def entities(
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by entity type."),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum rows to show."),
) -> None:
    """List entities stored in the database."""
    store = _open_store()
    try:
        rows = store.list_entities(entity_type=type, limit=limit)
    finally:
        store.close()

    if not rows:
        console.print("[yellow]No entities found.[/yellow]")
        return

    table = Table(box=box.SIMPLE_HEAVY, show_lines=False)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Type", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Properties")
    table.add_column("Created", style="dim", no_wrap=True)

    for e in rows:
        props = json.dumps(e.properties) if e.properties else ""
        table.add_row(e.id, e.entity_type, e.name, props, e.created_at.isoformat(timespec="seconds"))

    console.print(table)
    console.print(f"[dim]{len(rows)} row(s)[/dim]")


@app.command()
def links(
    subject: Optional[str] = typer.Option(None, "--subject", "-s", help="Filter by subject entity ID."),
    predicate: Optional[str] = typer.Option(None, "--predicate", "-p", help="Filter by predicate."),
    object: Optional[str] = typer.Option(None, "--object", "-o", help="Filter by object entity ID."),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum rows to show."),
) -> None:
    """List links stored in the database."""
    store = _open_store()
    try:
        rows = store.find_links(
            subject_id=subject,
            predicate=predicate,
            object_id=object,
            limit=limit,
        )
    finally:
        store.close()

    if not rows:
        console.print("[yellow]No links found.[/yellow]")
        return

    table = Table(box=box.SIMPLE_HEAVY, show_lines=False)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Subject ID", style="dim", no_wrap=True)
    table.add_column("Predicate", style="cyan bold")
    table.add_column("Object ID", style="dim", no_wrap=True)
    table.add_column("Properties")
    table.add_column("Created", style="dim", no_wrap=True)

    for lnk in rows:
        props = json.dumps(lnk.properties) if lnk.properties else ""
        table.add_row(
            lnk.id[:8],
            lnk.subject_id[:8],
            lnk.predicate,
            lnk.object_id[:8],
            props,
            lnk.created_at.isoformat(timespec="seconds"),
        )

    console.print(table)
    console.print(f"[dim]{len(rows)} row(s)[/dim]")


@app.command()
def shell() -> None:
    """Open an interactive SQL shell against the database."""
    import readline  # noqa: F401 — enables arrow-key editing on most platforms

    path = _db_path()
    conn = sqlite3.connect(path, isolation_level=None)
    console.print(f"[bold]SQLite shell[/bold] — [dim]{path}[/dim]")
    console.print("[dim]Enter SQL statements. Type 'exit' or Ctrl-D to quit.[/dim]\n")
    buf: list[str] = []
    while True:
        prompt = "   > " if buf else "sql> "
        try:
            line = input(prompt)
        except EOFError:
            print()
            break
        if not buf and line.strip().lower() in ("exit", "quit", r"\q"):
            break
        buf.append(line)
        joined = " ".join(buf)
        if joined.rstrip().endswith(";"):
            try:
                cursor = conn.execute(joined)
                result = cursor.fetchall()
                desc = cursor.description
                if desc:
                    t = Table(box=box.SIMPLE_HEAVY)
                    for col in desc:
                        t.add_column(col[0])
                    for row in result:
                        t.add_row(*[str(v) if v is not None else "" for v in row])
                    console.print(t)
                else:
                    console.print("[green]OK[/green]")
            except Exception as exc:
                console.print(f"[red]{exc}[/red]")
            buf.clear()
    conn.close()


def main() -> None:
    app()
