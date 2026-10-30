import logging
from datetime import datetime
from uuid import UUID
from urllib.parse import urlsplit, urlunsplit
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, HttpUrl
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tool_registry.db import get_db
from tool_registry.security import validate_token
from toolmeta_harvester.db.models import HarvestSource


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
    "gitlab.com",
    "gitlab.ethz.ch",
}

GIT_SOURCE_DOMAINS = {
    "github.com",
    "gitlab.com",
    "gitlab.ethz.ch",
}


def matches_domain(hostname: str, domains: set[str]) -> bool:
    return any(
        hostname == domain or hostname.endswith(f".{domain}") for domain in domains
    )


def is_allowed_source(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname

        return (
            parsed.scheme.lower() in {"http", "https"}
            and hostname is not None
            and parsed.username is None
            and parsed.password is None
            and matches_domain(hostname.lower(), ALLOWED_SOURCE_DOMAINS)
        )
    except ValueError:
        return False


def normalize_source_url(url: str) -> str:
    url = url.strip()

    if not is_allowed_source(url):
        raise ValueError("Unsupported harvest source")

    parsed = urlsplit(url)
    hostname = parsed.hostname.lower()

    # Canonicalize HTTPS and remove default ports.
    scheme = "https"
    port = parsed.port

    if port not in (None, 80, 443):
        raise ValueError("Unsupported source port")

    path = parsed.path.rstrip("/")
    query = parsed.query

    if matches_domain(hostname, GIT_SOURCE_DOMAINS):
        if path.lower().endswith(".git"):
            path = path[:-4]

        # Repository URLs don't need query parameters.
        query = ""

    return urlunsplit((scheme, hostname, path, query, "")).lower()


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
    try:
        url = normalize_source_url(str(request.url))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

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
