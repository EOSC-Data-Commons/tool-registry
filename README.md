> 🚧 Work in Progress  
> This project is currently under active development.  
> Features may change, and the API may not be stable yet.  
> Contributions and feedback are welcome!

# Roadmap

## 🚧 Phase 1 — Core Tool Management (Done)

- [x] Project scaffolding and initial architecture
- [x] API endpoint to query by file format extension
- [x] Authenticate users with EGI check-in
- [x] User info to manage tool ownership and permissions
- [x] API endpoint to add a new tool.
- [x] API endpoint to update/remove existing tools
- [x] API documentation (Swagger/OpenAPI)
- [x] Deployment to Warehouse

## 🚧 Phase 2 — Advanced Features (Current)
- [x] Refactor get endpoint to match new schema from toolmeta-harvester
- [x] Change way users publish tools from submitting a tool to submitting a URL to harvest
- [x] Store harvest URLs to be consumed by toolmeta-harvester/airflow
- [ ] Add new query parameters to GET endpoint to filter by
- [ ] Use embeddings to search tools by description


# Installation and Usage

## Prerequisites

- Python 3.12+
- Docker
- uv

## Credentials

Setup `config/.secrets.toml`

## Setup

```
make install
make run
```

# Register a tool

For registering a tool please take a look at [REGISTER_TOOL.md](REGISTER_TOOL.md)
