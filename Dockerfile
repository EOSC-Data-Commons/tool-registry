# FROM python:3.12.8-bookworm
#
# ENV PYTHONPATH=/app/src
#
# WORKDIR /app
#
# # Install uv.
# COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
#
# # Copy the application into the container.
# COPY src ./src
# COPY config/config.toml ./config/config.toml
# COPY pyproject.toml .
# COPY LICENSE .
# COPY README.md .
# COPY uv.lock .
#
# RUN mkdir -p /app/cache
#
# RUN pip install uvicorn
# RUN uv sync --locked
# CMD ["sh", "-c", "uv run uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8080}"]

FROM ghcr.io/astral-sh/uv:latest AS uv

FROM python:3.12.8-bookworm

ENV PYTHONPATH=/app/src
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=uv /uv /uvx /bin/

# Copy dependency files first for better layer caching.
COPY pyproject.toml uv.lock ./

# Install dependencies.
RUN uv sync --locked --no-dev

# Copy application source.
COPY src ./src
COPY config/config.toml ./config/config.toml
COPY LICENSE .
COPY README.md .

RUN mkdir -p /app/cache

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]

