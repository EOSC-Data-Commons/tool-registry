import logging
from contextlib import asynccontextmanager

from tool_registry.api import root, tools, sources
from tool_registry.config import (
    load_service_config,
    init_logging,
    get_app_version,
    load_db_config,
)
import tool_registry.security as security
from tool_registry.db import create_tables
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

init_logging()
logger = logging.getLogger(__name__)
service_config = load_service_config()
API_PREFIX = service_config.api_prefix
VERSION = get_app_version()
logger.info(f"Starting Tool Registry Service - Version: {VERSION}")
logger.debug(
    f"With db configuration: {load_db_config()} and service configuration: {service_config}"
)
security.init_nonce_db()
# ADMIN_TOKEN = security.generate_admin_token(service_config.admin_auth_key)
# logger.info(f"Admin token: {ADMIN_TOKEN}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(
    lifespan=lifespan,
)

app.include_router(root.router, prefix=API_PREFIX)
app.include_router(tools.router, tags=["Tools"], prefix=f"{API_PREFIX}/tools")
app.include_router(sources.router, tags=["Sources"], prefix=f"{API_PREFIX}/sources")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
