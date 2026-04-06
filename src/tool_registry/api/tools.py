import logging
from pydantic import BaseModel, field_validator
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy import any_, func, exists, literal, or_
from datetime import datetime
from toolmeta_models import ToolGeneric
from tool_registry.db import get_db
from tool_registry.security import validate_token, get_current_user


logger = logging.getLogger(__name__)
router = APIRouter()


class ToolOut(BaseModel):
    id: int
    uri: str
    location: str
    name: str
    description: Optional[str]
    license: Optional[str]
    keywords: Optional[list[str]]
    tags: Optional[list[str]]
    version: Optional[str]
    types: Optional[list[str]]
    input_file_formats: Optional[list[str]]
    output_file_formats: Optional[list[str]]
    input_file_descriptions: Optional[list[str]]
    output_file_descriptions: Optional[list[str]]
    input_slots: Optional[list[dict]]
    output_slots: Optional[list[dict]]

    class Config:
        from_attributes = True

class ToolOutExt(ToolOut):
    raw_definition: Optional[dict]
    raw_metadata: Optional[dict]
    metadata_schema: Optional[dict]
    metadata_version: Optional[str]
    metadata_type: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: str

class ToolCreate(BaseModel):
    uri: str
    name: str
    version: str
    location: Optional[str] = ""
    license: Optional[str] = ""
    description: str
    keywords: Optional[list[str]] = []
    tags: Optional[list[str]] = []
    types: Optional[list[str]]
    input_file_formats: Optional[List[str]] = []
    output_file_formats: Optional[List[str]] = []
    input_file_descriptions: Optional[List[str]] = []
    output_file_descriptions: Optional[List[str]] = []
    input_slots: Optional[List[dict]] = []
    output_slots: Optional[List[dict]] = []
    raw_definition: Optional[dict] = {}
    raw_metadata: Optional[dict] = {}
    metadata_schema: Optional[dict] = {}
    metadata_version: Optional[str] = ""
    metadata_type: Optional[str] = ""

    @field_validator("input_file_formats", "output_file_formats", mode="before")
    @classmethod
    def normalize_formats(cls, v):
        if not v:
            return []
        return [fmt.lstrip(".").lower() for fmt in v if fmt]

class ToolUpdate(BaseModel):
    uri: Optional[str] = None
    location: Optional[str] = None
    name: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    types: Optional[list[str]]
    input_file_formats: Optional[List[str]] = None
    output_file_formats: Optional[List[str]] = None
    input_file_descriptions: Optional[List[str]] = None
    output_file_descriptions: Optional[List[str]] = None
    input_slots: Optional[List[dict]] = None
    output_slots: Optional[List[dict]] = None
    raw_definition: Optional[dict] = None
    raw_metadata: Optional[dict] = None
    metadata_schema: Optional[dict] = None
    metadata_version: Optional[str] = None
    metadata_type: Optional[str] = None

    @field_validator("input_file_formats", "output_file_formats", mode="before")
    @classmethod
    def normalize_formats(cls, v):
        if v is None:
            return None
        return [fmt.lstrip(".").lower() for fmt in v if fmt]

    model_config = {
        "extra": "forbid"
    }

class ToolSearchParams(BaseModel):
    name: Optional[str] = None
    input_format: Optional[str] = None
    output_format: Optional[str] = None
    archetype: Optional[str] = None
    user_info: Optional[dict] = None


async def get_tool_by_id(
    id: int, db: AsyncSession
) -> Optional[ToolGeneric]:
    query = select(ToolGeneric).where(
        ToolGeneric.id == id)
    result = await db.execute(query)
    tool = result.scalars().first()
    return tool

async def get_tool_by_user(
    user: str, db: AsyncSession
) -> Optional[ToolGeneric]:
    query = select(ToolGeneric).where(
        ToolGeneric.created_by == user)
    result = await db.execute(query)
    tool = result.scalars().first()
    return tool

async def search_tools_in_db(
    search: ToolSearchParams, db: AsyncSession
) -> list[ToolGeneric]:
    query = select(ToolGeneric)
    logger.debug(f"Starting tool search with parameters: {search.model_dump()}")
    if search.name:
        logger.debug(f"Searching for tools with name like: {search.name}")
        query = query.where(
            ToolGeneric.name.ilike(f"%{search.name}%"))
    if search.archetype:
        logger.debug(f"Filtering tools by archetype: {search.archetype}")
        # query = query.where(
        #     ToolGeneric.archetype == search.archetype
        # )
        query = query.where(
            search.archetype == any_(ToolGeneric.types)
        )
    if search.user_info:
        logger.debug(f"Filtering tools by creator: {search.user_info['user']}")
        query = query.where(
            ToolGeneric.created_by == search.user_info["user"]
        )
    if search.input_format:
        pattern = f"%{search.input_format}%"

        # LATERAL-style unnest
        unnested = func.unnest(ToolGeneric.input_file_descriptions).alias("desc")

        description_match = exists(
            select(literal(1))
            .select_from(unnested)
            .where(unnested.column.ilike(pattern))
        )

        format_match = search.input_format == any_(ToolGeneric.input_file_formats)

        query = query.where(
            or_(format_match, description_match)
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
    archetype: Optional[str] = Query(
        None,
        description="Filter tools by archetype.",
        example="galaxy_workflow",
    ),
    db: AsyncSession = Depends(get_db),
    user_info=Depends(get_current_user)
):
    """
    Search for tools based on provided criteria.
    """
    search = ToolSearchParams(
        name=name,
        input_format=input_format,
        output_format=output_format,
        archetype=archetype,
        user_info=user_info,
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
    identifier: int = Path(
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
    tool = await get_tool_by_id(identifier, db)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    logger.debug(f"Retrieved tool: {tool.name} (UUID: {tool.id})")
    return ToolOutExt.from_orm(tool)


@router.delete("/{identifier}", description="Delete a tool by id.", tags=["Tools"])
async def delete_tool(identifier: int = Path(..., description="The internal id of the tool to delete.", example="5"),
                      user_info=Depends(validate_token),  
                      db: AsyncSession = Depends(get_db)):
    tool = await get_tool_by_id(identifier, db)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    if tool.created_by != user_info["user"]:
        raise HTTPException(status_code=403, detail="You do not have permission to delete this tool")
    await db.delete(tool)
    await db.commit()
    return {"message": "Tool deleted successfully"}

@router.post("/", description="Create a new tool in the registry.", tags=["Tools"])
async def create_tool(tool_data: ToolCreate, 
                      user_info=Depends(validate_token),  
                      db: AsyncSession = Depends(get_db)):
    logger.debug(f"Received tool creation request with data: {tool_data.model_dump()}")
    new_tool = ToolGeneric(
        uri=tool_data.uri,
        location=tool_data.location,
        name=tool_data.name,
        version=tool_data.version,
        description=tool_data.description,
        types=tool_data.types,
        input_file_formats=tool_data.input_file_formats,
        output_file_formats=tool_data.output_file_formats,
        input_file_descriptions=tool_data.input_file_descriptions,
        output_file_descriptions=tool_data.output_file_descriptions,
        raw_metadata=tool_data.raw_metadata,
        metadata_schema=tool_data.metadata_schema,
        metadata_version=tool_data.metadata_version,
        metadata_type=tool_data.metadata_type,
        created_by=user_info["user"],
    )

    db.add(new_tool)
    await db.commit()
    await db.refresh(new_tool)

    return {"message": "Tool created successfully", "tool_id": new_tool.id}

@router.patch("/{identifier}", description="Update an existing tool.", tags=["Tools"])
async def update_tool(
    identifier: int,
    tool_data: ToolUpdate,
    user_info=Depends(validate_token),
    db: AsyncSession = Depends(get_db),
):
    logger.debug(f"Received tool update request for ID {identifier} with data: {tool_data.model_dump()}")
    # Fetch tool
    result = await db.execute(
        select(ToolGeneric).where(ToolGeneric.id == identifier)
    )
    tool = result.scalar_one_or_none()

    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    # Ownership check
    if tool.created_by != user_info["user"]:
        raise HTTPException(status_code=403, detail="Not allowed to update this tool")


    # Only update provided fields
    update_data = tool_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(tool, field, value)

    await db.commit()
    await db.refresh(tool)

    return {"message": "Tool updated successfully", "tool_id": tool.id}
