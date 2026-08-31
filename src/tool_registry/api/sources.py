import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, HttpUrl
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tool_registry.db import get_db
from tool_registry.models import HarvestSource


logger = logging.getLogger(__name__)
router = APIRouter()


class HarvestSourceCreate(BaseModel):
    url: HttpUrl
    schedule: str | None = None


class HarvestSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    schedule: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


@router.post(
    "",
    response_model=HarvestSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_source(
    request: HarvestSourceCreate,
    session: AsyncSession = Depends(get_db),
):
    source = HarvestSource(
        url=str(request.url),
        schedule=request.schedule,
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

    # return {"ok": True, "id": source.id, "url": source.url, "schedule": source.schedule}
    return source
