> 🚧 Work in Progress  
> This project is currently under active development.  
> Features may change, and the API may not be stable yet.  
> Contributions and feedback are welcome!

# Roadmap

## 🚧 Phase 1 — Core Tool Management (Current)

- [x] Project scaffolding and initial architecture
- [x] API endpoint to query by file format extension
- [x] Authenticate users with EGI check-in
- [x] User info to manage tool ownership and permissions
- [x] API endpoint to add a new tool.
- [x] API endpoint to update/remove existing tools
- [x] API documentation (Swagger/OpenAPI)
- [ ] Basic tests and CI pipeline
- [ ] Deployment to Warehouse

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
