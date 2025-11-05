# Tool Registry

Summary
-------
Tool Registry is a reference implementation and specification to publish, curate, and expose value‑adding services, workflows, and tools in a managed registry. The service exposes a small HTTP API that reads tool descriptors (JSON files) from a configured directory and returns listings or single tool metadata.

Functionalities
---------------
- List all supported tools:
  - Method: `GET`
  - Endpoint: `/tools/`
  - Response: JSON array of objects with `toolURI`, `toolLabel`, and `toolDescription`.

- Retrieve a single tool by identifier:
  - Method: `GET`
  - Endpoint: `/tools/{identifier}`
  - Supported identifier formats:
    - `edc:fil.<...>` — match by file type (`typeURI`).
    - `edc:tool.<...>` — match by tool URI (`toolURI`).
  - Response: JSON object with either `typeURI` or `toolURI` plus `toolLabel`, `toolDescription`. Returns `{}` when not found.

- Root (public) endpoints:
  - Method: `GET`
  - Endpoint: `/` — API root (see `src/tool_registry/api/root.py` for behavior).
  - Method: `GET`
  - Endpoint: `/{filter_by}` — additional public filters (implementation dependent).

Authentication
--------------
- Endpoints use an API key. Provide the key with an HTTP `Authorization` header:
  - `Authorization: Bearer <TOOL_REGISTRY_API_KEY>`
- The key is read from application settings (`app_settings.TOOL_REGISTRY_API_KEY`).

Configuration / Environment Variables
-------------------------------------
- `TOOL_REGISTRY_API_KEY` — required API key for protected endpoints.
- `SUPPORTED_TOOLS_DIR` — directory path containing `.json` tool descriptor files.
- `EXPOSE_PORT` — port for the HTTP server (default `2005`).
- `APP_NAME` — optional application name.

uv (astral-sh) package manager
-------------------------------

uv is a lightweight tool used in this project to create a Python virtual environment and install dependencies from the `uv.lock` file. See the project repository: `https://github.com/astral-sh/uv`.

How this project uses `uv`
- The `Dockerfile` pulls the `ghcr.io/astral-sh/uv:latest` image and runs:
  - `uv venv .venv` — create a virtual environment at `./.venv`.
  - `uv sync --frozen --no-cache` — install pinned dependencies from `uv.lock` into the venv.
- Local workflow uses the same two commands to reproduce the runtime environment locally.

Install and use `uv` on macOS

1) Recommended — use the official container (no local install required)
- Create venv:
  - `docker run --rm -v $(pwd):/work -w /work ghcr.io/astral-sh/uv:latest uv venv .venv`
- Sync dependencies:
  - `docker run --rm -v $(pwd):/work -w /work ghcr.io/astral-sh/uv:latest uv sync --frozen --no-cache`

2) Install the `uv` binary (manual or Homebrew)

- Option A — Install via Homebrew (recommended on macOS)
  - If the `astral-sh/uv` tap is available:
    - `brew tap astral-sh/uv`
    - `brew install astral-sh/uv/uv`
  - If a core/homebrew formula exists for your Homebrew installation (try this first):
    - `brew install uv`
  - Verify installation:
    - `uv --version`
  - Notes:
    - On Apple Silicon (M1/M2), Homebrew prefix is typically `/opt/homebrew`; binaries installed by Homebrew are placed in the Homebrew `bin` directory and do not require `sudo`.

- Option B — Install the `uv` binary (manual)
  - Determine architecture (optional):
    - `uname -m`  \# `arm64` for Apple Silicon, `x86_64` for Intel
  - Download the appropriate macOS binary from `https://github.com/astral-sh/uv/releases` (choose the release and the `darwin` binary matching your architecture).
    - Example (replace `<TAG>` and `<arch>` with the release tag and architecture):
      - `curl -Lo uv https://github.com/astral-sh/uv/releases/download/<TAG>/uv-darwin-<arch>`
  - Make it executable and move it into your PATH:
    - `chmod +x uv`
    - Move to a directory in your PATH:
      - Intel/macOS (default Homebrew location on Intel): `sudo mv uv /usr/local/bin/uv`
      - Apple Silicon (Homebrew default): `mv uv /opt/homebrew/bin/uv`  \# may require `sudo` depending on permissions
  - Verify:
    - `uv --version`

3) Using `uv` locally
- Create venv: `uv venv .venv`
- Activate venv (optional): `source .venv/bin/activate`
- Sync deps: `uv sync --frozen --no-cache`


Files of interest
-----------------
- `pyproject.toml` — project metadata and dependencies.
- `README.md` — this file.
- `Dockerfile` — container build instructions.
- `src/main.py` — application entrypoint and FastAPI app configuration.
- `src/tool_registry/api/public.py` — tools public API implementation.
- `supported-tools/` — (not in repo) expected directory for tool JSON files.

Tool descriptor format
----------------------
- Each supported tool is a JSON file in `SUPPORTED_TOOLS_DIR`.
- Minimal fields used by the API:
  - `toolURI` (string) — unique tool identifier.
  - `toolProperties` (object) — may contain `toolLabel` and `toolDescription`.
  - `typeURI` (array|string) — optional types for matching `edc:fil.*`.

Dockerize
-----------
- Build the Docker image:
- ```bash
  docker build -t tool-registry-service .
    ```
- Run the container:
- ```bash
    docker run -d -p 2005:2005 -e TOOL_REGISTRY_API
_KEY=your_api_key_here tool-registry-service
    ```


Examples
--------
List all tools:

```bash
curl -H "Authorization: Bearer your_api_key_here" http://localhost:2005/tools/
   ```

Get a tool by tool URI:

```bash
curl -H "Authorization: Bearer your_api_key_here" http://localhost:2005/tools/edc:tool.example_tool

```
Get a tool by file type:

```bash
curl -H "Authorization: Bearer your_api_key_here" http://localhost:2005/tools/edc:fil.example_type
```

License
-------
-------
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
