### splash-ml is now splash_links!
The older mongo version of splash-ml has been tagged as `v0.1.0`. No new features will be added to this, though bug fixes are possible.

Starting with v1.0.0, splash_links is now based on SQL and has many new features, including native Tiled integration.


# splash_links

A FastAPI service for storing and querying directed, predicate-labeled relationships between arbitrary entities — like a lightweight triplestore, without SPARQL.

Relationships are stored in a SQL database (SQLite by default, PostgreSQL for production) and exposed through a [GraphQL](https://graphql.org/) API built with [Strawberry](https://strawberry.rocks/).

This service stories any link with a `uri`. It is expected to work very well with Tiled.

## Concepts

The data model is simple:

- **Entity** — a named node with a `type` and optional JSON `properties`
- **Link** — a directed edge from a *subject* entity to an *object* entity, labelled with a *predicate* string and optional JSON `properties`
- **Embedding** — a vector attached to an entity, with a model label and optional JSON metadata

Example: `(Experiment "SAXS run 42") --[produced]--> (Dataset "raw_001.h5")`

## Running the service

### With pixi (recommended)

[Install pixi](https://pixi.sh/latest/#installation), then:

```bash
pixi install          # resolve and install the environment (first time only)
pixi run serve        # start the dev server at http://localhost:8080
```

The GraphQL search tool is available at **http://localhost:8080/splash_links/graphql**.

Set `SPLASH_LINKS_DB` to a file path to persist data across restarts (defaults to `links.sqlite` when launched via `pixi run serve`):

```bash
SPLASH_LINKS_DB=/data/links.sqlite pixi run serve
```

### With Docker

```bash
docker build -t splash-links -f Containerfile .
docker run -p 8080:8080 -v $(pwd)/data:/data \
  -e SPLASH_LINKS_DB=/data/links.sqlite \
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

### Create an embedding

```bash
MODEL_ID=$(curl -X POST http://localhost:8080/splash_links/embedding-models \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "text-embedding-3-small",
    "version": "1",
    "description": "Example model metadata"
  }' | jq -r '.id')

curl -X POST http://localhost:8080/splash_links/embeddings \
  -H 'Content-Type: application/json' \
  -d '{
    "entityId": "<entity-id>",
    "embeddingModelId": "'"$MODEL_ID"'",
    "vector": [0.12, -0.03, 0.88],
    "properties": {"chunk": 1}
  }'
```

### Find nearest embeddings

Embedding CRUD uses REST. Nearest-neighbor search stays in GraphQL and uses cosine distance. For PostgreSQL, embeddings are stored in a native `pgvector` column; for SQLite, they are stored as compact binary blobs and searched in-process.

```graphql
query {
  nearestEmbeddings(
    vector: [0.11, -0.02, 0.90]
    embeddingModelId: "<embedding-model-id>"
    limit: 5
  ) {
    distance
    embedding {
      id
      entityId
      embeddingModel { name version }
      entity { name }
    }
  }
}
```

### Fetch or delete embeddings

```bash
curl http://localhost:8080/splash_links/embeddings/<embedding-id>
curl 'http://localhost:8080/splash_links/embedding-models?name=text-embedding-3-small'
curl 'http://localhost:8080/splash_links/embeddings?entityId=<entity-id>&embeddingModelId=<embedding-model-id>'
curl -X DELETE http://localhost:8080/splash_links/embeddings/<embedding-id>
```

### Health check

```
GET /health  →  {"status": "ok"}
```

## Inspecting the database

The `splash-links` CLI lets you view stored data and open a raw SQLite shell without needing to run the server.

All commands read the database from `$SPLASH_LINKS_DB` (defaulting to `links.sqlite` in the current directory).

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

### List embeddings

```bash
pixi run embeddings -- --entity <entity-id>
splash-links embeddings --model-id <embedding-model-id> --limit 10
```

### Raw SQLite shell

```bash
pixi run db
# or directly:
splash-links shell
```

This opens an interactive SQLite prompt. Useful queries:

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
| `embeddings` | `pixi run embeddings` | List embeddings in the database |
| `db` | `pixi run db` | Open raw SQLite interactive shell |

Pass extra flags after `--`, e.g. `pixi run entities -- --type Experiment --limit 5`.

### Project structure

```
src/splash_links/
    __init__.py   — package exports
    store.py      — abstract Store interface + SQLiteStore implementation
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

### Database backends

The service is built on SQLAlchemy 2.x and supports multiple backends. The active backend is selected by the `SPLASH_LINKS_DB` environment variable, which accepts any SQLAlchemy connection URL (or a plain file path / `:memory:` shorthand for SQLite).

#### SQLite (recommended for local installations)

SQLite is the default and the **recommended choice for most deployments**. It requires no external server, is trivially portable (a single file), and handles the read-heavy workloads typical of this service well.

```bash
SPLASH_LINKS_DB=links.sqlite pixi run serve
# or a bare path — the service auto-converts it to sqlite:///…
SPLASH_LINKS_DB=/data/links.sqlite pixi run serve
```

#### PostgreSQL with pgvector

PostgreSQL nearest-neighbor search uses the `pgvector` extension. The Alembic migration will create the extension automatically when permissions allow it.

```bash
SPLASH_LINKS_DB=postgresql+psycopg2://user:pass@host/dbname pixi run serve
```

Embeddings use dialect-specific storage. PostgreSQL stores them in a native `pgvector` column, while SQLite stores packed float32 data in a BLOB. Base64 is intentionally not used, since it would only increase storage size and parsing overhead.

#### PostgreSQL (recommended for production / multi-user deployments)

Use PostgreSQL when you need concurrent writes, role-based access control, or want to run the service behind a load balancer. A `docker-compose.yml` is provided that starts a Postgres instance alongside the application:

```bash
docker compose up --build
```

Supply an explicit URL for an external Postgres cluster:

```bash
SPLASH_LINKS_DB="postgresql+psycopg2://user:pass@host/dbname" pixi run serve
```

Alembic migrations are applied automatically on startup regardless of backend.

#### DuckDB (experimental — performance testing only)

DuckDB support is **experimental** and intended for comparing analytical query performance against SQLite, not for production use. It is not covered by the test suite and may have compatibility gaps.

```bash
SPLASH_LINKS_DB="duckdb:///links.duckdb" pixi run serve
```

| Backend | Use case | Status |
|---------|----------|--------|
| SQLite | Local / single-user installations | ✅ Recommended |
| PostgreSQL | Production / multi-user deployments | ✅ Supported |
| DuckDB | Analytical performance benchmarking | ⚠️ Experimental |

### CI

GitHub Actions (`.github/workflows/build-app.yml`) runs lint and tests on every push and pull request to `main`. The test step enforces the 90% coverage requirement — the build fails if coverage drops below that threshold.
