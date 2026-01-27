import logging
from logging.config import dictConfig
from dynaconf import Dynaconf
from dataclasses import dataclass

settings = Dynaconf(
    settings_files=["config/config.toml", "config/.secrets.toml"])


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    name: str


@dataclass(frozen=True)
class ServiceConfig:
    name: str
    listen_port: int
    bind_address: str
    api_prefix: str
    admin_auth_key: str


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            # "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            "format": "%(levelname)s | %(name)s | %(message)s",
        },
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "loggers": {
        "": {  # root logger
            "handlers": ["default"],
            "level": "INFO",
        },
        "uvicorn": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.error": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


def init_logging() -> None:
    dictConfig(LOGGING_CONFIG)
    # log_level = settings.logging.log_level.upper()
    #
    # log_format = (
    #     "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    #     if settings.logging.use_detailed_format
    #     else "%(levelname)s - %(message)s"
    # )
    # logging.basicConfig(level=log_level, format=log_format)


def load_service_config() -> ServiceConfig:
    return ServiceConfig(
        name=settings.service.name,
        listen_port=settings.service.listen_port,
        bind_address=settings.service.bind_address,
        api_prefix=settings.service.api_prefix,
        admin_auth_key=settings.service.admin_auth_key,
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
