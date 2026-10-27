# EOSC Data Commons — Tool Registry

> **Under active development.** The API and data model may change between releases.

The **Tool Registry** is a FastAPI service for discovering scientific software, workflows and computational tools in the [EOSC Data Commons](https://github.com/EOSC-Data-Commons) ecosystem. It exposes structured tool metadata harvested from public repositories and provides keyword, metadata, file-format, semantic and dataset-driven matching.

Rather than requiring users to submit a complete metadata record, the registry accepts a URL pointing to an existing public software record or repository. The separate [toolmeta-harvester](https://github.com/EOSC-Data-Commons/toolmeta-harvester) pipeline processes sources and populates the shared PostgreSQL tool catalogue.

## Capabilities

- **Browse and filter tools** by name, description, source, category/type, keyword and minimum metadata quality score.
- **Retrieve detailed metadata** including provenance, identifiers, licenses, software requirements, runtime platforms, input/output parameters and preserved source metadata.
- **Match tools to files** by declared MIME type or filename extension, with `and`/`or` matching.
- **Semantic tool search** using EGI-hosted `nomic-embed-text-v2-moe` embeddings and vector cosine similarity.
- **Match tools to datasets** by generating task-oriented search queries using an LLM, performing semantic retrieval and combining rankings with reciprocal rank fusion (RRF).
- **Register harvest sources** by submitting a supported public URL using EGI Check-in or a short-lived administrator token.
- **OpenAPI documentation** generated automatically by FastAPI.

## Architecture

```text
Public research software sources
  GitHub · GitLab · Zenodo · WorkflowHub · bio.tools
                    │
                    ▼
          toolmeta-harvester
          (harvesting, normalization,
           indexing and embeddings)
                    │
                    ▼
       PostgreSQL tool catalogue
       ├── ToolMetadata
       ├── ToolEmbedding (pgvector)
       └── harvest_source
                    ▲
                    │
             Tool Registry API
       ├── GET  /api/v1/tools/
       ├── GET  /api/v1/tools/{id}
       ├── POST /api/v1/tools/match
       └── POST /api/v1/sources
                    ▲
                    │
       Web clients / API clients / services
```

The API and harvester are separate applications sharing tool metadata models and database storage. Registering a source saves a URL for harvesting; it does **not** synchronously harvest the submitted resource.

## Installation and running with Docker Compose

### Prerequisites

- [Docker Engine](https://docs.docker.com/engine/) with the [Docker Compose plugin](https://docs.docker.com/compose/)
- An accessible PostgreSQL database provisioned with the shared `toolmeta-harvester` schema, vector support, and BM25 search functionality
- An [EGI LLM service](https://llm.ai.egi.eu/) API key for semantic and dataset matching

The Compose configuration starts **only the registry API**. It does not run PostgreSQL, harvest tools, provision database extensions, or generate embeddings. Set up and populate the catalogue separately using [toolmeta-harvester](https://github.com/EOSC-Data-Commons/toolmeta-harvester).

### 1. Clone the repository

```bash
git clone https://github.com/EOSC-Data-Commons/tool-registry.git
cd tool-registry
```

### 2. Configure the service

Create a `.env` file next to `docker-compose.yaml` with the values needed by the existing Compose configuration:

```dotenv
TOOL_REGISTRY_DATABASE__HOST=your-postgres-host
TOOL_REGISTRY_DATABASE__PORT=5432
TOOL_REGISTRY_DATABASE__NAME=tooldb
TOOL_REGISTRY_DATABASE__USER=harvester
TOOL_REGISTRY_DATABASE__PASSWORD=replace-me
TOOL_REGISTRY_LOGGING__LOG_LEVEL=INFO
TOOL_REGISTRY_EGI__LLM_API_KEY=replace-me
BASE_DIR=/app
```

Use a PostgreSQL hostname reachable **from inside the container**. `localhost` inside the registry container refers to that container, not to a database on the Docker host. For example, use the database service name if it shares a Docker network, or an appropriate reachable host address for an external PostgreSQL server.

Do not commit `.env` or other secrets. The application reads its nonsecret defaults from `config/config.toml` using Dynaconf; additional settings can be supplied through the `TOOL_REGISTRY_...` environment variable convention.

### 3. Build and start

```bash
docker compose up -d --build
```

The existing `docker-compose.yaml` does **not** publish a host port. If you want to access the API directly from your local machine, add the following to the `tool-registry` service in `docker-compose.yaml`:

```yaml
services:
  tool-registry:
    ports:
      - "8080:8080"
```

This is a fragment to **merge into the existing service**, not a replacement for the whole Compose file. The image runs Uvicorn on container port `8080`. After adding the port mapping, apply it with:

```bash
docker compose up -d
```

With this mapping, the API is available at:

- Swagger UI: <http://localhost:8080/docs>
- OpenAPI JSON: <http://localhost:8080/openapi.json>
- Health endpoint: <http://localhost:8080/api/v1/health>

For deployments behind a reverse proxy, configure networking and routing there instead of publishing a host port.

### Operations

```bash
docker compose ps                  # Inspect service status
docker compose logs -f tool-registry # Follow API logs
docker compose up -d --build      # Rebuild and recreate after changes
docker compose restart tool-registry # Restart the service
docker compose down               # Stop and remove Compose containers
```

The application writes its runtime cache to `./cache`, which Compose bind-mounts at `/app/cache`. Database content is **not** managed or persisted by this Compose project.

## API reference

All paths below use the default `/api/v1` prefix. Read-only search endpoints are public; source registration requires bearer authentication.

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/v1/` | Service welcome response |
| `GET` | `/api/v1/health` | Health/version information (not a deep dependency health check) |
| `GET` | `/api/v1/auth` | Validate a bearer token and return the authenticated user |
| `GET` | `/api/v1/egi-token-portal` | Return the configured EGI token portal URL |
| `GET` | `/api/v1/tools/` | Search/filter tools with pagination |
| `GET` | `/api/v1/tools/sources` | List distinct source domains present in tool metadata |
| `GET` | `/api/v1/tools/{identifier}` | Retrieve full metadata for a tool UUID |
| `GET` | `/api/v1/tools/{identifier}/categories` | List extracted types and classifications for a tool |
| `POST` | `/api/v1/tools/match` | File, semantic or dataset matching |
| `POST` | `/api/v1/sources` | Register a URL for future harvesting (authenticated) |

### Search tools

```bash
curl -G 'http://localhost:8080/api/v1/tools/' \
  --data-urlencode 'keyword=genomics' \
  --data-urlencode 'type=galaxy' \
  --data-urlencode 'limit=10' \
  --data-urlencode 'offset=0'
```

The search supports the following query parameters:

| Parameter | Description | Default |
| --- | --- | --- |
| `name` | Title/name BM25 search | — |
| `description` | Description BM25 search | — |
| `type` | Exact membership of normalized `search_types` | — |
| `keyword` | Case-insensitive substring match on keywords | — |
| `source` | Source hostname (for example `github.com`) | — |
| `quality_score` | Minimum metadata quality score, from 0 to 1 | — |
| `limit` | Maximum records, from 1 to 1000 | `100` |
| `offset` | Pagination offset, nonnegative | `0` |
| `all` | Disable pagination when `true` | `false` |

The response is a **JSON array** of compact tool records, not a `{results: ...}` wrapper. It also sets `X-Total-Count` and pagination `Link` headers. Note that current `Link` headers use `/tools` rather than the configured API prefix, so clients should build their own pagination URLs from the original endpoint until this is corrected.

### Retrieve tool metadata

```bash
curl 'http://localhost:8080/api/v1/tools/TOOL_UUID'

curl 'http://localhost:8080/api/v1/tools/TOOL_UUID/categories'

curl 'http://localhost:8080/api/v1/tools/sources'
```

Individual tool responses include descriptive metadata, provenance, software categories, programming languages, runtime platforms, software requirements, input/output descriptions, timestamps, quality score and raw metadata. The exact fields depend on the harvested source and shared schema.

### Match tools by supported files

The `file` matching mode compares the supplied MIME types to declared tool input `encoding_format` values and falls back to filename-extension matching against input identifiers.

```bash
curl -X POST 'http://localhost:8080/api/v1/tools/match' \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "file",
    "inputs": [
      {"name": "samples.csv", "mime_type": "text/csv"},
      {"name": "metadata.json", "mime_type": "application/json"}
    ],
    "options": {"operator": "or"}
  }'
```

Use `"operator": "and"` to require a tool to match every requested file; `or` (the default) accepts at least one matching file. This mode checks metadata already in the database and does not inspect or upload actual files.

### Semantic matching

```bash
curl -X POST 'http://localhost:8080/api/v1/tools/match' \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "semantic",
    "query": "software for molecular docking of proteins",
    "category": "galaxy",
    "limit": 10
  }'
```

This embeds the query using the EGI embedding endpoint and ranks stored `description` embeddings by cosine distance. `category` is optional and filters the candidate tools by normalized category before ranking. The request limit is 1–100 (default 20).

Stored vectors must be generated with the configured embedding model (`nomic-embed-text-v2-moe`) and compatible `search_document:` prefix; query vectors use `search_query:`. With no category filter, the current code requests `limit * 3` candidates, so the returned array may exceed the requested limit. With a category filter, a materialized prefiltered set is searched and the supplied limit is enforced.

### Match tools to a dataset description

```bash
curl -X POST 'http://localhost:8080/api/v1/tools/match' \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "dataset",
    "description": "A dataset containing longitudinal RNA sequencing measurements across different experimental conditions.",
    "limit": 10
  }'
```

In this mode the registry:

1. Sends the dataset description to the EGI-hosted chat model to produce up to five software-capability search queries.
2. Converts each query into a vector embedding.
3. Runs one semantic retrieval per query, optionally filtered by `category`.
4. Merges the results using **reciprocal rank fusion**, with score `1 / (60 + rank)` per query ranking.
5. Returns up to `limit` compact tool records.

Generated queries are cached on disk for 30 days. The cache key includes the dataset description, LLM model and prompt version. This operation uses remote LLM services and is not a purely local search.

### Register a harvest source

Publish software at a supported public source, then submit the source URL with a bearer token:

```bash
curl -X POST 'http://localhost:8080/api/v1/sources' \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${EGI_ACCESS_TOKEN}" \
  -d '{"url": "https://github.com/example/my-tool"}'
```

A successful request returns **HTTP 201** and a source record containing its UUID, URL, schedule, enabled state and timestamps. An already-registered URL returns **409 Conflict**; an unsupported source domain returns **400 Bad Request**; missing or invalid credentials return **401 Unauthorized**.

Allowed source domains currently include `github.com`, `gitlab.com`, `gitlab.ethz.ch`, `zenodo.org`, `bio.tools` and `workflowhub.eu` (including subdomains). Acceptance of a domain does not guarantee that the harvester can access every record on it. See [REGISTER_TOOL.md](REGISTER_TOOL.md) for publication guidance.

## Authentication

The registry supports bearer tokens from **EGI Check-in** (production, development or demo environment) and short-lived, HMAC-signed administrator tokens.

For EGI authentication, obtain a valid access token through the configured EGI AAI token portal. The API checks the issuer and signature against the configured EGI JWKS endpoint and retrieves user information. Check the configured portal with:

```bash
curl 'http://localhost:8080/api/v1/egi-token-portal'
```

Check authentication with:

```bash
curl 'http://localhost:8080/api/v1/auth' \
  -H "Authorization: Bearer ${EGI_ACCESS_TOKEN}"
```

For local administration, the repository includes an administrator-token script. Administrator tokens have a short acceptance window (60 seconds of clock skew) and use a SQLite nonce store to reject replay. Generate them immediately before use. Ensure `cache/` exists and remains writable.

## Implementation notes and limitations

- **Searching and publishing are decoupled.** Posting a source registers it; scheduled harvest and embedding generation must be handled by the harvester pipeline.
- **Full schema provisioning is external.** The application creates its own tables, but the shared catalogue schema, vector facilities, BM25 functions/indexes and initial data must already be available.
- **Name and description ranking use database-specific BM25 functionality.** A plain PostgreSQL instance may not support these operators and functions without the corresponding extension/index setup.
- **Vector-search category filters have different performance characteristics.** A category filter materializes matching embeddings before ranking; the unfiltered path can use an approximate vector index.
- **File matching currently loads candidate tools and performs checks in Python**, which may be costly for a large catalogue.
- **Semantic query embedding uses a synchronous function within an asynchronous endpoint**, which can block the event loop; dataset mode offloads embedding creation to a thread.
- **Current search pagination links omit the API prefix and active filters.** Rely on `X-Total-Count` and construct URLs from your original query.
- **CORS is currently permissive.** Restrict allowed origins for production deployment, especially where authenticated browser clients are involved.
- **Avoid logging secrets.** Review startup DEBUG logging of database configuration before using it in production.

## Related projects

- [toolmeta-harvester](https://github.com/EOSC-Data-Commons/toolmeta-harvester) — metadata harvesting, normalization, storage and embedding generation.
- [REGISTER_TOOL.md](REGISTER_TOOL.md) — guide to publishing and registering tool sources.
- [EOSC Data Commons](https://github.com/EOSC-Data-Commons) — wider project ecosystem.

## License

Apache License 2.0. See [LICENSE](LICENSE).
