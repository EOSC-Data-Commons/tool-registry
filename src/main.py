import logging

from tool_registry.api import root, tools
from tool_registry.config import load_service_config, init_logging
from tool_registry.security import ADMIN_TOKEN

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

init_logging()
logger = logging.getLogger(__name__)
service_config = load_service_config()
API_PREFIX = service_config.api_prefix

logger.info(f"Admin token: {ADMIN_TOKEN}")

app = FastAPI(
    # title=project_details["title"],
    # description=project_details["description"],
    # version=f"{project_details['version']} (Build Date: {build_date})",
)

app.include_router(root.router, prefix=API_PREFIX)
app.include_router(tools.router, tags=["Tools"], prefix=f"{API_PREFIX}/tools")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
