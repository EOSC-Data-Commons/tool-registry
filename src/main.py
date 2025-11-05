import logging
import os
import sys
# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["BASE_DIR"] = os.getenv("BASE_DIR", base_dir)

from src.tool_registry.api import root, public

from akmi_utils.commons import build_date
from akmi_utils import commons as a_commons

from contextlib import asynccontextmanager
from typing import Annotated

import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

import os


APP_NAME = os.environ.get("APP_NAME", "Tool Registry")
EXPOSE_PORT = os.environ.get("EXPOSE_PORT", 2005)
OTLP_GRPC_ENDPOINT = os.environ.get("OTLP_GRPC_ENDPOINT", "http://localhost:4317")


app_settings = a_commons.app_settings
print(app_settings.to_dict())



api_keys = [app_settings.TOOL_REGISTRY_API_KEY]
security = HTTPBearer()

def auth_header(
    request: Request,
    auth_cred: Annotated[HTTPAuthorizationCredentials, Depends(security)],
):
    if not auth_cred or auth_cred.credentials not in api_keys:
            return HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Forbidden"
            )
    return None


keys = ["name", "version", "description", "title"]
project_details = a_commons.get_project_details(keys, base_dir=os.environ.get("BASE_DIR"))
print(project_details)




@asynccontextmanager
async def lifespan(application: FastAPI):
    logging.info("start up")
    yield


app = FastAPI(
    title=project_details['title'],
    description=project_details['description'],
    version=f"{project_details['version']} (Build Date: {build_date})",
    lifespan=lifespan
)

app.include_router(root.router, tags=["Public"], prefix="")
app.include_router(public.router, tags=["Tools"], prefix="/tools")

@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return JSONResponse(status_code=404, content={"message": "Endpoint not found"})
    return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    num_workers = max(1, os.cpu_count() or 1)
    logging.info(f"=====Starting server with {num_workers} workers on port {EXPOSE_PORT} =====")
    print(f"Starting server with {num_workers} workers on port {EXPOSE_PORT}")

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=int(EXPOSE_PORT),
        workers=1,
        factory=False,
        reload=True,
    )