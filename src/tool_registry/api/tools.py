import logging
from pydantic import BaseModel
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy import any_
from datetime import datetime
from toolmeta_models import ToolGeneric
from tool_registry.db import get_db


logger = logging.getLogger(__name__)
router = APIRouter()


class ToolOut(BaseModel):
    id: int
    uri: str
    location: str
    name: str
    description: Optional[str]
    version: Optional[str]
    archetype: Optional[str]
    input_file_formats: Optional[list[str]]
    output_file_formats: Optional[list[str]]

    class Config:
        from_attributes = True

class ToolOutExt(ToolOut):
    raw_metadata: Optional[dict]
    metadata_schema: Optional[dict]
    metadata_version: Optional[str]
    metadata_type: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: str


class ToolSearchParams(BaseModel):
    name: Optional[str] = None
    input_format: Optional[str] = None
    output_format: Optional[str] = None
    tag: Optional[str] = None


async def get_tool_by_id(
    id: int, db: AsyncSession
) -> Optional[ToolGeneric]:
    query = select(ToolGeneric).where(
        ToolGeneric.id == id)
    result = await db.execute(query)
    tool = result.scalars().first()
    return tool


async def search_tools_in_db(
    search: ToolSearchParams, db: AsyncSession
) -> list[ToolGeneric]:
    query = select(ToolGeneric)
    if search.name:
        logger.info(f"Searching for tools with name like: {search.name}")
        query = query.where(
            ToolGeneric.name.ilike(f"%{search.name}%"))
    if search.input_format:
        query = query.where(
            search.input_format == any_(ToolGeneric.input_file_formats)
        )
    if search.output_format:
        query = query.where(
            search.output_format == any_(ToolGeneric.output_file_formats)
        )
    logger.debug(f"Executing tool search with query: {query}")
    result = await db.execute(query)
    tools = result.scalars().all()
    return tools


@router.get(
    "/",
    response_model=list[ToolOut],
    tags=["Tools"],
    description="Search for tools given query parameters.",
)
async def search_tools(
    name: Optional[str] = Query(
        None,
        description="Partial match for tool name.",
        example="genomic",
    ),
    input_format: Optional[str] = Query(
        None,
        description="Filter tools by input format.",
        example="fasta",
    ),
    output_format: Optional[str] = Query(
        None,
        description="Filter tools by output format.",
        example="cram",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Search for tools based on provided criteria.
    """
    search = ToolSearchParams(
        name=name,
        input_format=input_format,
        output_format=output_format,
    )
    tools = await search_tools_in_db(search, db)
    logger.debug(f"Found {len(tools)} tools matching search criteria.")
    return [ToolOut.from_orm(tool) for tool in tools]


@router.get(
    "/{identifier}",
    response_model=ToolOutExt,
    description="Retrieve a single tool by uuid.",
    tags=["Tools"],
)
async def get_tools_by_identifier(
    identifier: str = Path(
        ...,
        description="The internal id of the tool to retrieve.",
        example="5",
    ),
    db: AsyncSession = Depends(get_db),
):
    logger.debug(f"Received request to retrieve tool with ID: {identifier}")
    """
    Retrieve a single tool by its ID.
    """
    tool = await get_tool_by_id(int(identifier), db)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    logger.debug(f"Retrieved tool: {tool.name} (UUID: {tool.id})")
    return ToolOutExt.from_orm(tool)
