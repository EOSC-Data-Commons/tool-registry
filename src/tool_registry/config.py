import logging
from dynaconf import Dynaconf
from dataclasses import dataclass
import tomllib

settings = Dynaconf(
    envvar_prefix="TOOL_REGISTRY",
    settings_files=["config/config.toml", "config/.secrets.toml"],
)

# Environment variable overrides:
# export TOOL_REGISTRY_DATABASE__HOST=localhost
# export TOOL_REGISTRY_DATABASE__PORT=5432
# export TOOL_REGISTRY_DATABASE__NAME=admin
# export TOOL_REGISTRY_DATABASE__USER=harvester
# export TOOL_REGISTRY_DATABASE__PASSWORD=yoursecretsecret
# export TOOL_REGISTRY_SERVICE__EGI_ENV=development


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    name: str


@dataclass(frozen=True)
class ServiceConfig:
    admin_auth_key: str
    name: str = "Tool Registry Service"
    listen_port: int = 8080
    bind_address: str = "0.0.0.0"
    api_prefix: str = "/api/v1"
    egi_env: str = "production"


@dataclass(frozen=True)
class AIModelConfig:
    llm_model: str
    llm_options: dict
    embedding_model: str
    embedding_options: dict
    embedding_type: str


@dataclass(frozen=True)
class EndPoint:
    url: str
    key: str


def get_app_version() -> str:
    try:
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)

        return data["project"]["version"]
    except Exception as e:
        logging.error(f"Failed to read version from pyproject.toml: {e}")
        return "unknown"


def init_logging() -> None:
    log_level = settings.logging.log_level.upper()

    log_format = (
        "%(asctime)s - %(name)s - %(levelname)s:    %(message)s"
        if settings.logging.use_detailed_format
        else "%(levelname)s:    %(message)s"
    )
    logging.basicConfig(level=log_level, format=log_format)


def load_service_config() -> ServiceConfig:
    return ServiceConfig(
        name=settings.service.name,
        listen_port=settings.service.listen_port,
        bind_address=settings.service.bind_address,
        api_prefix=settings.service.api_prefix,
        admin_auth_key=settings.service.admin_auth_key,
        egi_env=settings.service.egi_env,
    )


def load_ai_config() -> AIModelConfig:
    cfg = settings.ai_model
    return AIModelConfig(
        llm_model=cfg.llm_model,
        llm_options=cfg.llm_options,
        embedding_model=cfg.embedding_model,
        embedding_options=cfg.embedding_options,
        embedding_type=cfg.embedding_type,
    )


def load_db_config() -> dict:
    db = settings.database
    return DatabaseConfig(
        host=db.host,
        port=db.port,
        user=db.user,
        password=db.password,
        name=db.name,
    )


def get_llm_endpoint() -> EndPoint:
    cfg = settings.ai_ep
    return EndPoint(url=cfg.llm_api, key=cfg.llm_api_key)


def get_embedding_endpoint() -> EndPoint:
    cfg = settings.ai_ep
    return EndPoint(url=cfg.embedding_api, key=cfg.embedding_api_key)
