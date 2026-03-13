# splash_links

A FastAPI service for storing and querying directed, predicate-labeled relationships between arbitrary entities — like a lightweight triplestore, without SPARQL.

Relationships are stored in [DuckDB](https://duckdb.org/) (with an eye toward [pgduck](https://github.com/duckdb/pg_duckdb) in the future) and exposed through a [GraphQL](https://graphql.org/) API built with [Strawberry](https://strawberry.rocks/).

## Concepts

The data model is simple:

- **Entity** — a named node with a `type` and optional JSON `properties`
- **Link** — a directed edge from a *subject* entity to an *object* entity, labelled with a *predicate* string and optional JSON `properties`

Example: `(Experiment "SAXS run 42") --[produced]--> (Dataset "raw_001.h5")`

## Running the service

### With pixi (recommended)

[Install pixi](https://pixi.sh/latest/#installation), then:

```bash
pixi install          # resolve and install the environment (first time only)
pixi run serve        # start the dev server at http://localhost:8080
```

The GraphiQL IDE is available at **http://localhost:8080/graphql**.

Set `SPLASH_LINKS_DB` to a file path to persist data across restarts (defaults to `links.duckdb` when launched via `pixi run serve`):

```bash
SPLASH_LINKS_DB=/data/links.duckdb pixi run serve
```

### With Docker

```bash
docker build -t splash-links .
docker run -p 8080:8080 -v $(pwd)/data:/data \
  -e SPLASH_LINKS_DB=/data/links.duckdb \
  splash-links
```

## Using the API

Open **http://localhost:8080/graphql** in a browser to use the GraphiQL IDE.

### Create entities

```graphql
mutation {
  createEntity(input: { entityType: "Experiment", name: "SAXS run 42", properties: { beamline: "12.3.1" } }) {
    id
    name
    entityType
  }
}
```

### Create a link between entities

```graphql
mutation {
  createLink(input: { subjectId: "<experiment-id>", predicate: "produced", objectId: "<dataset-id>" }) {
    id
    predicate
    subject { name }
    object  { name }
  }
}
```

### Query entities and traverse the graph

```graphql
{
  entity(id: "<experiment-id>") {
    name
    outgoingLinks {
      predicate
      object { name entityType }
    }
  }
}
```

### Filter links

```graphql
{
  links(predicate: "produced", subjectId: "<experiment-id>") {
    id
    object { name }
  }
}
```

### Health check

```
GET /health  →  {"status": "ok"}
```

## Inspecting the database

The `splash-links` CLI lets you view stored data and open a raw DuckDB shell without needing to run the server.

All commands read the database from `$SPLASH_LINKS_DB` (defaulting to `links.duckdb` in the current directory).

### List entities

```bash
pixi run entities                      # all entities
pixi run entities -- --type Experiment # filter by type
pixi run entities -- --limit 10        # cap results
```

### List links

```bash
pixi run links                              # all links
pixi run links -- --predicate produced      # filter by predicate
pixi run links -- --subject <entity-id>     # outgoing from a node
pixi run links -- --object  <entity-id>     # incoming to a node
```

### Raw DuckDB shell

```bash
pixi run db
# or directly:
splash-links shell
```

This opens an interactive DuckDB prompt. Useful queries:

```sql
SELECT * FROM entities;
SELECT * FROM links WHERE predicate = 'produced';
SELECT e.name, l.predicate, o.name AS object
  FROM links l
  JOIN entities e ON e.id = l.subject_id
  JOIN entities o ON o.id = l.object_id;
```

## Client CLI (GraphQL)

The client API is also available as a Typer CLI for talking to a running splash-links service.

You can run it either through the existing root command:

```bash
splash-links client --help
```

or directly via the standalone script:

```bash
splash-links-client --help
```

Set `SPLASH_LINKS_URI` (default: `splash://localhost:8080`) to point at your service.

### Create an entity

```bash
splash-links client create-entity \
  --entity-type Experiment \
  --name "SAXS run 42" \
  --properties '{"beamline":"12.3.1"}'
```

### Create a link

```bash
splash-links client create-link \
  <subject-id> produced <object-id> \
  --properties '{"confidence":0.99}'
```

### Find links for an entity

```bash
splash-links client find-links <entity-id> --predicate produced --limit 20
```


## Developer setup

### Prerequisites

- [pixi](https://pixi.sh/latest/#installation)

### Install and run tests

```bash
git clone https://github.com/als-computing/splash_links.git
cd splash_links
pixi install
pixi run test
```

Tests require ≥ 90% coverage and will fail the build if that threshold is not met.

### Pixi tasks

| Task | Command | Description |
|------|---------|-------------|
| `serve` | `pixi run serve` | Start dev server with auto-reload on port 8080 |
| `test` | `pixi run test` | Run pytest with coverage (≥90% required) |
| `lint` | `pixi run lint` | Ruff lint check |
| `fmt` | `pixi run fmt` | Ruff format |
| `docs` | `pixi run docs` | Serve MkDocs site locally |
| `entities` | `pixi run entities` | List entities in the database |
| `links` | `pixi run links` | List links in the database |
| `db` | `pixi run db` | Open raw DuckDB interactive shell |

Pass extra flags after `--`, e.g. `pixi run entities -- --type Experiment --limit 5`.

### Project structure

```
src/splash_links/
    __init__.py   — package exports
    store.py      — abstract Store interface + DuckDBStore implementation
    schema.py     — Strawberry GraphQL types, queries, mutations
    app.py        — FastAPI app factory (create_app)
    main.py       — uvicorn entry point
    cli.py        — Typer CLI (entities, links, shell commands)

_tests/
    test_service.py  — integration tests (store unit tests + GraphQL HTTP tests)

pixi.toml        — environment definition and task shortcuts
pyproject.toml   — package metadata, ruff config, coverage config
Dockerfile       — two-stage build (pixi build → debian:bookworm-slim runtime)
```

### Storage and future backends

The `Store` ABC in `store.py` decouples the service from DuckDB. To target Postgres via pgduck (or any other SQL backend), implement the same interface and pass an instance to `create_app`. The DuckDB file path is controlled by the `SPLASH_LINKS_DB` environment variable.

### CI

GitHub Actions (`.github/workflows/build-app.yml`) runs lint and tests on every push and pull request to `main`. The test step enforces the 90% coverage requirement — the build fails if coverage drops below that threshold.

