> 🚧 Work in Progress  
> This project is currently under active development.  
> Features may change, and the API may not be stable yet.  
> Contributions and feedback are welcome!

# Roadmap

## 🚧 Phase 1 — Core Tool Management (Current)
- [x] Project scaffolding and initial architecture
- [x] API endpoint to query by file format extension
- [x] Authenticate users with EGI check-in
- [ ] User table to manage tool ownership and permissions
- [ ] API endpoint to add a new tool with metadata and contract
- [ ] API endpoint to update/remove existing tools
- [ ] API documentation (Swagger/OpenAPI)
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
