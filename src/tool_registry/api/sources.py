import logging
from datetime import datetime
from uuid import UUID
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, HttpUrl
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tool_registry.db import get_db
from tool_registry.models import HarvestSource
from tool_registry.security import validate_token


logger = logging.getLogger(__name__)
router = APIRouter()


class HarvestSourceCreate(BaseModel):
    url: HttpUrl
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://zenodo.org/record/1234567",
            }
        }
    )


class HarvestSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    schedule: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


ALLOWED_SOURCE_DOMAINS = {
    "zenodo.org",
    "github.com",
    "bio.tools",
    "workflowhub.eu",
}


def is_allowed_source(url: str) -> bool:
    hostname = urlparse(url).hostname

    if not hostname:
        return False

    hostname = hostname.lower()

    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in ALLOWED_SOURCE_DOMAINS
    )


@router.post(
    "",
    description="Create a new harvest source",
    response_model=HarvestSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_source(
    request: HarvestSourceCreate,
    user_info=Depends(validate_token),
    session: AsyncSession = Depends(get_db),
):
    url = str(request.url)

    if not is_allowed_source(url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported harvest source",
        )

    source = HarvestSource(
        url=url,
        # schedule=request.schedule,
    )
    logger.info("Creating harvest source: %s", source.url)

    session.add(source)

    try:
        await session.commit()
        await session.refresh(source)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Harvest source already exists",
        )

    return source
