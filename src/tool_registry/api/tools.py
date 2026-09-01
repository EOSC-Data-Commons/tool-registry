import logging
from pydantic import BaseModel, field_validator, Field
from typing import Optional, List, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, exists, literal, select, or_, cast
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import ConfigDict

from toolmeta_harvester.db.models import ToolMetadata
from tool_registry.db import get_db


logger = logging.getLogger(__name__)
router = APIRouter()


class ToolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID

    quality_score: float | None = None

    # Provenance
    source_identifier: str | None = None
    source_url: str | None = None
    metadata_url: str | None = None
    metadata_format: str
    metadata_version: str | None = None

    # CodeMeta / schema.org core
    title: str | None = None
    description: str | None = None
    raw_description: str | None = None
    version: str | None = None
    license: str | None = None

    identifiers: list[str]

    url: str | None = None
    code_repository: str | None = None

    keywords: list[str]
    authors: list[dict[str, Any]]
    organizations: list[dict[str, Any]]
    types: list[str]

    programming_languages: list[dict[str, Any]]
    runtime_platforms: list[dict[str, Any]]
    software_requirements: list[dict[str, Any]]

    # Scientific extensions
    software_types: list[dict[str, Any]]
    consumes_data: list[dict[str, Any]]
    produces_data: list[dict[str, Any]]

    # RO-Crate inputs / outputs
    inputs: list[dict[str, Any]]
    outputs: list[dict[str, Any]]

    # Source preservation
    raw_metadata: dict[str, Any]

    harvested_at: datetime
    pipeline_tag: str | None = None

    date_created: datetime | None = None
    date_published: datetime | None = None
    date_modified: datetime | None = None


class ToolOutExt(ToolOut):
    raw_definition: Optional[dict]
    raw_metadata: Optional[dict]
    metadata_schema: Optional[dict]
    metadata_version: Optional[str]
    metadata_type: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]


class ToolSearchParams(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    type: Optional[str] = None
    keyword: Optional[str] = None
    quality_score: Optional[float] = None
    limit: int = 100
    offset: int = 0
    all: bool = False


class FileInput(BaseModel):
    name: str
    mime_type: str


class MatchOptions(BaseModel):
    operator: Optional[Literal["or", "and"]] = "or"


class ToolMatchRequest(BaseModel):
    type: Literal["file"]  # extensible later
    inputs: List[FileInput] = Field(..., min_items=1)
    options: Optional[MatchOptions] = None


async def get_tool_by_field(
    field: str,
    value: Any,
    db: AsyncSession,
) -> ToolMetadata | None:
    column = getattr(ToolMetadata, field, None)

    if column is None:
        raise ValueError(f"Unknown ToolMetadata field: {field}")

    query = select(ToolMetadata).where(column == value)
    result = await db.execute(query)

    return result.scalars().first()


def jsonb_array_object_matches(
    column,
    value: str,
    keys: tuple[str, ...] = (
        "name",
        "alternate_name",
        "id",
        "identifier",
        "url",
    ),
):
    element = func.jsonb_array_elements(column).table_valued("value").alias("element")

    json_value = cast(element.c.value, JSONB)
    pattern = f"%{value}%"

    return exists(
        select(1)
        .select_from(element)
        .where(or_(*[json_value[key].astext.ilike(pattern) for key in keys]))
    )


def text_array_matches(column, value: str):
    element = func.unnest(column).alias("element")

    return exists(
        select(1).select_from(element).where(element.column.ilike(f"%{value}%"))
    )


async def search_tools_in_db(
    search: ToolSearchParams, db: AsyncSession
) -> list[ToolMetadata]:
    query = select(ToolMetadata)
    logger.debug(f"Starting tool search with parameters: {search.model_dump()}")
    if search.title:
        logger.debug(f"Searching for tools with name like: {search.title}")
        query = query.where(ToolMetadata.title.ilike(f"%{search.title}%"))
    if search.description:
        logger.debug(f"Searching for tools with description like: {search.description}")
        query = query.where(ToolMetadata.description.ilike(f"%{search.description}%"))
    if search.type:
        logger.debug(f"Searching for tools with type like: {search.type}")
        query = select(ToolMetadata).where(
            or_(
                text_array_matches(
                    ToolMetadata.types,
                    search.type,
                ),
                jsonb_array_object_matches(
                    ToolMetadata.programming_languages,
                    search.type,
                ),
                jsonb_array_object_matches(
                    ToolMetadata.runtime_platforms,
                    search.type,
                ),
                jsonb_array_object_matches(
                    ToolMetadata.software_types,
                    search.type,
                ),
            )
        )
    if search.keyword:
        pattern = f"%{search.keyword}%"
        unnested = func.unnest(ToolMetadata.keywords).alias("keyword")
        keyword_match = exists(
            select(literal(1))
            .select_from(unnested)
            .where(unnested.column.ilike(pattern))
        )
        query = query.where(keyword_match)

    if search.source:
        query = query.where(ToolMetadata.source_url.ilike(f"%://{search.source}/%"))

    if search.quality_score is not None:
        query = query.where(ToolMetadata.quality_score >= search.quality_score)

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    if not search.all:
        query = query.limit(search.limit).offset(search.offset)

    logger.debug(f"Executing tool search with query: {query}")
    result = await db.execute(query)
    tools = result.scalars().all()
    return (tools, total)


@router.get(
    "/",
    response_model=list[ToolOut],
    tags=["Tools"],
    description="Search for tools given query parameters.",
)
async def search_tools(
    request: Request,
    response: Response,
    title: Optional[str] = Query(
        None,
        description="Partial match for tool title/name.",
        example="genomic",
    ),
    description: Optional[str] = Query(
        None,
        description="Partial match for tool description.",
        example="alignment",
    ),
    type: Optional[str] = Query(
        None,
        description="Filter tools by type (e.g., 'galaxy', 'scipion', 'ComputationalWorkflow').",
        example="galaxy",
    ),
    keyword: Optional[str] = Query(
        None,
        description="Filter tools by keyword.",
        example="covid-19",
    ),
    source: Optional[str] = Query(
        None,
        description="Filter tools by source domain (e.g., github.com, zenodo.org)",
        example="workflowhub.eu",
    ),
    quality_score: Optional[float] = Query(
        None,
        description="Filter tools by quality score (0.0 to 1.0).",
        ge=0.0,
        le=1.0,
    ),
    limit: Optional[int] = Query(
        100, ge=1, le=1000, description="Maximum number of results to return."
    ),
    offset: Optional[int] = Query(
        0, ge=0, description="Number of results to skip for pagination."
    ),
    all: Optional[bool] = Query(
        False,
        description="If true, ignore pagination and return all results (overrides limit and offset).",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Search for tools based on provided criteria.
    """
    search = ToolSearchParams(
        title=title,
        description=description,
        keyword=keyword,
        type=type,
        source=source,
        quality_score=quality_score,
        limit=limit,
        offset=offset,
        all=all,
    )
    allowed_params = set(ToolSearchParams.model_fields)

    unknown_params = set(request.query_params.keys()) - allowed_params

    if unknown_params:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown query parameter(s): {', '.join(sorted(unknown_params))}",
        )

    tools, total = await search_tools_in_db(search, db)

    response.headers["X-Total-Count"] = str(total)

    if not all:
        links = []

        # next
        if offset + limit < total:
            next_offset = offset + limit
            links.append(f'</tools?limit={limit}&offset={next_offset}>; rel="next"')

        # prev
        if offset > 0:
            prev_offset = max(offset - limit, 0)
            links.append(f'</tools?limit={limit}&offset={prev_offset}>; rel="prev"')

        # first
        links.append(f'</tools?limit={limit}&offset=0>; rel="first"')

        # last
        last_offset = max(((total - 1) // limit) * limit, 0)
        links.append(f'</tools?limit={limit}&offset={last_offset}>; rel="last"')

        response.headers["Link"] = ", ".join(links)
    else:
        # optional explicit indicator pagination is disabled
        response.headers["Pagination"] = "disabled"

    logger.debug(f"Found {len(tools)} tools matching search criteria.")
    return [ToolOut.from_orm(tool) for tool in tools]


@router.get(
    "/sources",
    description="Get a list of unique source domains from the tools.",
    response_model=list[str],
)
async def get_source_domains(
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    domain = func.split_part(
        func.split_part(ToolMetadata.source_url, "://", 2),
        "/",
        1,
    )

    query = (
        select(domain.label("domain"))
        .where(ToolMetadata.source_url.is_not(None))
        .distinct()
        .order_by(domain)
    )

    result = await db.execute(query)

    return list(result.scalars().all())


@router.get(
    "/{identifier}",
    response_model=ToolOut,
    description="Retrieve a single tool by id.",
    tags=["Tools"],
)
async def get_tools_by_identifier(
    identifier: str = Path(
        ...,
        description="The internal uuid of the tool to retrieve.",
        example="5f8d7c3e-9b1a-4f2e-8c3b-1a2b3c4d5e6f",
    ),
    db: AsyncSession = Depends(get_db),
):
    logger.debug(f"Received request to retrieve tool with ID: {identifier}")
    """
    Retrieve a single tool by its ID.
    """
    tool = await get_tool_by_field("id", identifier, db)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    logger.debug(f"Retrieved tool: {tool.title} (ID: {tool.id})")
    return ToolOut.from_orm(tool)
