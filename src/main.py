import logging

from tool_registry.api import root, tools
from tool_registry.config import load_service_config, init_logging
import tool_registry.security as security
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

init_logging()
logger = logging.getLogger(__name__)
service_config = load_service_config()
API_PREFIX = service_config.api_prefix
security.init_nonce_db()
ADMIN_TOKEN = security.generate_admin_token(service_config.admin_auth_key)
# isValid = security.validate_admin_token(ADMIN_TOKEN, service_config.admin_auth_key)  # Verify the admin token on startup
isValid = True
logger.info(f"Admin token: {ADMIN_TOKEN}") if isValid else logger.error("Admin token is invalid on startup.") 
    # logger.info(f"Admin token: {ADMIN_TOKEN}")

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
