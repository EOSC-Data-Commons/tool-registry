
import logging
from fastapi import APIRouter, Depends 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, distinct, func
from toolmeta_models import ToolGeneric
from tool_registry.db import get_db


logger = logging.getLogger(__name__)
router = APIRouter()
async def list_unique_file_types(session):
    input_formats = (
        select(func.unnest(ToolGeneric.input_file_formats).label("file_type"))
        .where(ToolGeneric.input_file_formats.is_not(None))
    )

    output_formats = (
        select(func.unnest(ToolGeneric.output_file_formats).label("file_type"))
        .where(ToolGeneric.output_file_formats.is_not(None))
    )

    unioned = input_formats.union(output_formats).subquery()

    result = await session.execute(
        select(distinct(unioned.c.file_type))
        .where(unioned.c.file_type.is_not(None))
        .order_by(unioned.c.file_type)
    )

    return result.scalars().all()

async def list_unique_tool_types(session):
    subq = (
        select(
            func.unnest(ToolGeneric.types).label("tool_type")
        )
        .where(ToolGeneric.types.is_not(None))
        .subquery()
    )

    result = await session.execute(
        select(subq.c.tool_type)
        .distinct()
        .order_by(subq.c.tool_type)
    )

    return result.scalars().all()

@router.get("/files")
async def get_file_types(
    db: AsyncSession = Depends(get_db),
):
    file_types = await list_unique_file_types(db)

    return {
        "file_types": file_types,
        "count": len(file_types),
    }

@router.get("/tools")
async def get_tool_types(
    db: AsyncSession = Depends(get_db),
):
    tool_types = await list_unique_tool_types(db)

    return {
        "tool_types": tool_types,
        "count": len(tool_types),
    }
