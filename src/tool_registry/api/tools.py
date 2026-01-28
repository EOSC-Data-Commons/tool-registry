import logging
from pydantic import BaseModel
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists, func, literal_column
from sqlalchemy import any_
from toolmeta_harvester.db.models import GalaxyWorkflowArtifact
from tool_registry.db import get_db


logger = logging.getLogger(__name__)
router = APIRouter()


class ToolOut(BaseModel):
    id: int
    uuid: str
    name: str
    description: Optional[str]
    url: str
    version: Optional[str]
    input_formats: Optional[list[str]]
    output_formats: Optional[list[str]]
    input_toolshed_tools: Optional[list[str]]
    output_toolshed_tools: Optional[list[str]]
    toolshed_tools: Optional[list[str]]
    tags: Optional[list[str]]

    class Config:
        from_attributes = True


class ToolSearchParams(BaseModel):
    name: Optional[str] = None
    input_format: Optional[str] = None
    output_format: Optional[str] = None
    tag: Optional[str] = None


async def get_galaxy_tool_by_uuid(
    uuid: str, db: AsyncSession
) -> Optional[GalaxyWorkflowArtifact]:
    query = select(GalaxyWorkflowArtifact).where(
        GalaxyWorkflowArtifact.uuid == uuid)
    result = await db.execute(query)
    tool = result.scalars().first()
    return tool


async def search_galaxy_tools(
    search: ToolSearchParams, db: AsyncSession
) -> list[GalaxyWorkflowArtifact]:
    query = select(GalaxyWorkflowArtifact)
    if search.name:
        logger.info(f"Searching for tools with name like: {search.name}")
        query = query.where(
            GalaxyWorkflowArtifact.name.ilike(f"%{search.name}%"))
    if search.input_format:
        query = query.where(
            search.input_format == any_(GalaxyWorkflowArtifact.input_formats)
        )
    if search.output_format:
        query = query.where(
            search.output_format == any_(GalaxyWorkflowArtifact.output_formats)
        )
    if search.tag:
        tag = literal_column("tag")
        query = query.where(
            exists(
                select(1)
                .select_from(func.unnest(GalaxyWorkflowArtifact.tags).alias("tag"))
                .where(tag.ilike(f"%{search.tag}%"))
            )
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
    tag: Optional[str] = Query(
        None,
        description="Filter tools by tag.",
        example="covid",
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
        tag=tag,
    )
    tools = await search_galaxy_tools(search, db)
    logger.debug(f"Found {len(tools)} tools matching search criteria.")
    return [ToolOut.from_orm(tool) for tool in tools]


@router.get(
    "/{identifier}",
    response_model=ToolOut,
    description="Retrieve a single tool by uuid.",
    tags=["Tools"],
)
async def get_tools_by_identifier(
    identifier: str = Path(
        ...,
        description="The UUID of the tool to retrieve.",
        example="123e4567-e89b-12d3-a456-426614174000",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve a single tool by its UUID.
    """
    tool = await get_galaxy_tool_by_uuid(identifier, db)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    logger.debug(f"Retrieved tool: {tool.name} (UUID: {tool.uuid})")
    return ToolOut.from_orm(tool)
