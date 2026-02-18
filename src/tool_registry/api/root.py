import logging
from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse
from tool_registry.security import validate_token

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    logging.info("favicon route")
    return JSONResponse(status_code=404, content={"message": "favicon.ico Not found"})


@router.get("/", include_in_schema=False)
async def root():
    # lazy import to avoid circular import with `src.main`
    # from src.main import project_details

    logger.info("root route")
    return JSONResponse(
        status_code=200,
        content={
            "message": "Welcome to the Tool Registry API Service",
            # "version": project_details["version"],
            # "build_date": build_date,
            # "app_name": project_details["title"],
        },
    )


@router.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}


@router.get("/auth", tags=["Authentication"])
async def auth_check(
    user_info=Depends(validate_token),
):
    if user_info:
        return user_info

    return JSONResponse(status_code=401, content={"message": "Unauthorized"})
