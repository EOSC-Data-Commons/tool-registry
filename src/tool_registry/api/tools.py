import logging
import re
import asyncio
import hashlib
import json
from diskcache import Cache
from collections import defaultdict
from pathlib import Path as FilePath
from pydantic import BaseModel, Field, ValidationInfo, model_validator
from typing import Annotated, Literal
from typing import Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Path,
    Request,
    Response,
    Body,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, exists, literal, select, or_, cast, text
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import ConfigDict

from toolmeta_harvester.db.models import ToolEmbedding, ToolMetadata
from tool_registry.db import get_db
# from sqlalchemy.orm import Session

from toolmeta_harvester.tasks.embedding import embed
from tool_registry.config import egi_llm_api_key
from tool_registry import ai


EMBEDDING_MODEL = "nomic-embed-text-v2-moe"
EMBEDDING_TYPE = "description"
EMBEDDING_API = "https://llm.ai.egi.eu/embeddings"
EGI_LLM_API_KEY = egi_llm_api_key()


logger = logging.getLogger(__name__)
router = APIRouter()


cache = Cache("cache/llm-cache")


def cache_key(description: str) -> str:
    data = json.dumps(
        {
            "description": description.strip(),
            "model": ai.LLM_MODEL,
            "prompt_version": ai.PROMPT_VERSION,
        },
        sort_keys=True,
    )
    return hashlib.sha256(data.encode()).hexdigest()


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
    # types: list[str]
    types: list[str] = Field(default_factory=list)

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

    @model_validator(mode="after")
    def populate_categories(self, info: ValidationInfo):
        if info.context and "types" in info.context:
            self.types = info.context["types"]
        return self


class ToolOutMin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID

    source_identifier: str | None = None
    source_url: str | None = None

    title: str | None = None
    description: str | None = None
    version: str | None = None
    license: str | None = None
    types: list[str] = Field(default_factory=list)

    inputs: list[dict[str, Any]]
    outputs: list[dict[str, Any]]

    @model_validator(mode="after")
    def populate_categories(self, info: ValidationInfo):
        if info.context and "types" in info.context:
            self.types = info.context["types"]
        return self


class ToolSearchParams(BaseModel):
    name: Optional[str] = None
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


class FileToolMatchRequest(BaseModel):
    type: Literal["file"]
    inputs: list[FileInput] = Field(..., min_length=1)
    options: MatchOptions | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "file",
                    "inputs": [
                        {
                            "name": "foo.json",
                            "mime_type": "application/json",
                        },
                        {
                            "name": "bar.csv",
                            "mime_type": "text/csv",
                        },
                    ],
                    "options": {
                        "operator": "or",
                    },
                }
            ]
        }
    )


class SemanticToolMatchRequest(BaseModel):
    type: Literal["semantic"]
    query: str = Field(..., min_length=2)
    category: str = Field(default=None)
    limit: int = Field(default=20, ge=1, le=100)
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "semantic",
                    "query": "software for molecular docking of proteins",
                    "limit": 10,
                }
            ]
        }
    )


class DatasetToolMatchRequest(BaseModel):
    type: Literal["dataset"]
    description: str = Field(..., min_length=2)
    category: str = Field(default=None)
    limit: int = Field(default=20, ge=1, le=100)
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "dataset",
                    "description": "Different amino acids (AAs) may exert distinct effects on postprandial glucose and insulin concentrations. A quantitative comparison of the effects of AAs on glucose and insulin kinetics in humans is currently lacking. PubMed was queried to identify intervention studies reporting glucose and insulin concentrations after acute ingestion and/or intravenous infusion of AAs in healthy adults and those living with obesity and/or type 2 diabetes (T2DM). The systematic literature search identified 55 studies that examined the effects of L-leucine, L-isoleucine, L-alanine, L-glutamine, L-arginine, L-lysine, glycine, L-proline, L-phenylalanine, L-glutamate, branched-chain AAs (i.e., L-leucine, L-isoleucine, and L-valine), and multiple individual L-AAs on glucose and insulin concentrations. Oral ingestion of most individual AAs induced an insulin response but did not alter glucose concentrations in healthy participants. Specific AAs (i.e., leucine and isoleucine) co-ingested with glucose exerted a synergistic effect on the postprandial insulin response and attenuated the glucose response compared to glucose intake alone in healthy participants. Oral AA ingestion as well as intravenous AA infusion was able to stimulate an insulin response and decrease glucose concentrations in T2DM and obese individuals. The extracted information is publicly available and can serve multiple purposes such as computational modeling.",
                    "limit": 10,
                }
            ]
        }
    )


ToolMatchRequest = Annotated[
    FileToolMatchRequest | SemanticToolMatchRequest | DatasetToolMatchRequest,
    Field(discriminator="type"),
]


def extract_all_types(tool: dict) -> list:
    values = []

    for field in (
        tool.types,
        tool.runtime_platforms,
        tool.programming_languages,
        tool.software_types,
        tool.software_requirements,
        tool.consumes_data,
        tool.produces_data,
    ):
        values.extend(extract_type_values(field))
    return list(dict.fromkeys(values))


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
    if search.name:
        logger.debug(f"Searching for tools with name: {search.name}")

        bm25_score = ToolMetadata.title.op("<@>")(
            func.to_bm25query(
                search.name,
                "ix_tool_metadata_title_bm25",
            )
        )

        query = query.order_by(None).order_by(bm25_score.asc())
    if search.description:
        logger.debug(f"Searching for tools with description: {search.description}")

        bm25_score = ToolMetadata.description.op("<@>")(
            func.to_bm25query(
                search.description,
                "ix_tool_metadata_description_bm25",
            )
        )

        query = query.order_by(bm25_score.asc())

    if search.type:
        term = search.type.strip().lower()

        logger.debug(f"Searching for tools with type: {term}")

        query = query.where(ToolMetadata.search_types.contains([term]))
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
    response_model=list[ToolOutMin],
    tags=["Tools"],
    description="Search for tools given query parameters.",
)
async def search_tools(
    request: Request,
    response: Response,
    name: Optional[str] = Query(
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
        name=name,
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
    # return [ToolOutMin.from_orm(tool) for tool in tools]
    return [
        ToolOutMin.model_validate(
            tool,
            context={"types": extract_all_types(tool)},
        )
        for tool in tools
    ]


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


def term_key(value: Any) -> str | None:
    """
    Produce a stable key for deduplicating canonical term objects.
    """
    if isinstance(value, str):
        return value

    if not isinstance(value, dict):
        return None

    return (
        value.get("id")
        or value.get("identifier")
        or value.get("url")
        or value.get("name")
    )


def unique_terms(
    values: list[Any],
) -> list[Any]:
    result = []
    seen = set()

    for value in values:
        key = term_key(value)

        if key is None:
            continue

        key = str(key)

        if key in seen:
            continue

        seen.add(key)
        result.append(value)

    return result


def extract_type_values(value):
    result = []

    def visit(item):
        if item is None:
            return

        if isinstance(item, str):
            result.append(item.lower())
            return

        if isinstance(item, list):
            for subitem in item:
                visit(subitem)
            return

        if not isinstance(item, dict):
            return

        # Prefer explicit type information first.
        if item.get("type"):
            visit(item["type"])
            return

        for key in (
            "name",
            "id",
            "identifier",
            "url",
        ):
            extracted = item.get(key)

            if extracted:
                visit(extracted)
                return

    visit(value)

    return result


@router.get(
    "/{identifier}/categories",
    description=(
        "Retrieve all type and classification values associated with a single tool."
    ),
    tags=["Tools"],
)
async def get_tool_types_by_identifier(
    identifier: str = Path(
        ...,
        description="The internal UUID of the tool.",
        example="5f8d7c3e-9b1a-4f2e-8c3b-1a2b3c4d5e6f",
    ),
    db: AsyncSession = Depends(get_db),
):
    tool = await get_tool_by_field(
        "id",
        identifier,
        db,
    )

    if not tool:
        raise HTTPException(
            status_code=404,
            detail="Tool not found",
        )

    # return tool.search_types
    return extract_all_types(tool)


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
    # return ToolOut.from_orm(tool)
    return ToolOut.model_validate(
        tool,
        context={"types": extract_all_types(tool)},
    )


def file_input_matches(
    requested: FileInput,
    tool_input: dict,
) -> bool:
    """Return True if a requested file matches a tool input."""

    # Prefer MIME type matching.
    if (
        requested.mime_type
        and tool_input.get("encoding_format")
        and requested.mime_type.lower() == tool_input["encoding_format"].lower()
    ):
        return True

    # Fall back to filename extension.
    requested_ext = FilePath(requested.name).suffix.lower()

    tool_id = tool_input.get("id", "")
    tool_ext = FilePath(tool_id).suffix.lower()

    if requested_ext and tool_ext:
        return requested_ext == tool_ext

    return False


def tool_matches_files(
    requested_inputs: list[FileInput],
    tool_inputs: list[dict],
    operator: str = "or",
) -> bool:
    """Match requested files against the declared inputs of a tool."""

    if not tool_inputs:
        return False

    matches = [
        any(file_input_matches(requested, tool_input) for tool_input in tool_inputs)
        for requested in requested_inputs
    ]

    if operator == "and":
        return all(matches)

    return any(matches)


async def match_tools_by_file(
    match: FileToolMatchRequest,
    db: AsyncSession,
) -> list[ToolMetadata]:
    stmt = select(ToolMetadata).where(ToolMetadata.inputs.is_not(None))

    result = await db.scalars(stmt)

    tools = result.all()

    operator = match.options.operator if match.options else "or"

    return [
        tool
        for tool in tools
        if tool_matches_files(
            match.inputs,
            tool.inputs,
            operator,
        )
    ]


def sanitize_tool_type(value: str | None) -> str | None:
    if not value:
        return None

    value = value.strip().lower()

    if not re.fullmatch(r"[a-z0-9_-]+", value):
        raise ValueError(f"Invalid tool type: {value!r}")

    return value


async def match_tools_semantically(match, db):
    query = match.query
    limit = match.limit
    tool_type = sanitize_tool_type(match.category)
    session = db
    query_vector = embed(
        [query],
        api_key=EGI_LLM_API_KEY,
        api_url=EMBEDDING_API,
        model=EMBEDDING_MODEL,
        prefix="search_query: ",
    )[0]

    distance = ToolEmbedding.vector.cosine_distance(query_vector)

    if tool_type:
        stmt = (
            select(ToolMetadata)
            .join(
                ToolEmbedding,
                ToolEmbedding.tool_id == ToolMetadata.id,
            )
            .where(
                ToolEmbedding.embedding_type == EMBEDDING_TYPE,
                ToolEmbedding.embedding_model == EMBEDDING_MODEL,
                ToolMetadata.search_types.contains([tool_type]),
            )
            .order_by(distance)
            .limit(limit)
        )
    else:
        stmt = (
            select(ToolMetadata)
            .join(
                ToolEmbedding,
                ToolEmbedding.tool_id == ToolMetadata.id,
            )
            .where(
                ToolEmbedding.embedding_type == EMBEDDING_TYPE,
                ToolEmbedding.embedding_model == EMBEDDING_MODEL,
            )
            .order_by(distance)
            .limit(limit)
        )

    # Debug generated SQL
    if logger.isEnabledFor(logging.DEBUG):
        compiled = stmt.compile(
            dialect=session.bind.dialect,
            compile_kwargs={"literal_binds": True},
        )

        explain_sql = f"EXPLAIN (ANALYZE, BUFFERS) {compiled}"

        result = await db.execute(text(explain_sql))

        plan = "\n".join(row[0] for row in result)

        logger.debug(
            "Semantic matching query plan:\n%s",
            plan,
        )

    result = await session.scalars(stmt)
    return list(result.all())


async def match_tools_by_dataset_description(match, db):
    key = cache_key(match.description)
    tool_type = sanitize_tool_type(match.category)

    if (cached := cache.get(key)) is not None:
        queries = cached
    else:
        queries = await ai.dataset_to_tool_queries(
            match.description,
            api_key=EGI_LLM_API_KEY,
        )
        cache.set(cache_key(match.description), queries, expire=60 * 60 * 24 * 30)

    logger.debug(
        "Generated tool search queries:\n%s",
        json.dumps(queries, indent=2, ensure_ascii=False),
    )

    vectors = await asyncio.to_thread(
        embed,
        [q["query"] for q in queries],
        api_key=EGI_LLM_API_KEY,
        api_url=EMBEDDING_API,
        model=EMBEDDING_MODEL,
        prefix="search_query: ",
    )

    rankings = []

    for vector in vectors:
        distance = ToolEmbedding.vector.cosine_distance(vector)

        if tool_type:
            # This does not use HNSW index because of the pre-filtering.
            # Which means it scans all the vectors (filtered) to find the nearest.
            # With large filtered set it might become expensive to search.
            filtered_embeddings = (
                select(
                    ToolEmbedding.tool_id,
                    ToolEmbedding.vector,
                )
                .join(
                    ToolMetadata,
                    ToolMetadata.id == ToolEmbedding.tool_id,
                )
                .where(
                    ToolEmbedding.embedding_type == EMBEDDING_TYPE,
                    ToolEmbedding.embedding_model == EMBEDDING_MODEL,
                    ToolMetadata.search_types.contains([tool_type]),
                )
                .cte("filtered_embeddings")
                .prefix_with("MATERIALIZED")
            )

            distance = filtered_embeddings.c.vector.cosine_distance(vector)

            stmt = (
                select(ToolMetadata)
                .join(
                    filtered_embeddings,
                    filtered_embeddings.c.tool_id == ToolMetadata.id,
                )
                .order_by(distance)
                .limit(match.limit)
            )
        else:
            # If no tool_type is defined use the fast approximate HNSW index to search
            # for close vectors
            stmt = (
                select(ToolMetadata)
                .join(
                    ToolEmbedding,
                    ToolEmbedding.tool_id == ToolMetadata.id,
                )
                .where(
                    ToolEmbedding.embedding_type == EMBEDDING_TYPE,
                    ToolEmbedding.embedding_model == EMBEDDING_MODEL,
                )
                .order_by(distance)
                .limit(match.limit * 3)
            )

        result = await db.scalars(stmt)
        rankings.append(list(result.all()))

    # Reciprocal Rank Fusion
    scores = defaultdict(float)
    tools = {}

    for ranking in rankings:
        seen = set()

        for rank, tool in enumerate(ranking, start=1):
            if tool.id in seen:
                continue
            seen.add(tool.id)

            scores[tool.id] += 1 / (60 + rank)
            tools[tool.id] = tool

    ranked_ids = sorted(
        scores,
        key=scores.get,
        reverse=True,
    )

    return [tools[tool_id] for tool_id in ranked_ids[: match.limit]]


@router.post(
    "/match",
    response_model=list[ToolOutMin],
    description="Semantically match tools using an AI embedding search.",
    tags=["Tools"],
)
async def match_tools_post(
    match: Annotated[
        ToolMatchRequest,
        Body(
            openapi_examples={
                "file": {
                    "summary": "File matching",
                    "description": "Match tools by supported input file types.",
                    "value": {
                        "type": "file",
                        "inputs": [
                            {
                                "name": "foo.json",
                                "mime_type": "application/json",
                            },
                            {
                                "name": "bar.csv",
                                "mime_type": "text/csv",
                            },
                        ],
                        "options": {
                            "operator": "or",
                        },
                    },
                },
                "semantic": {
                    "summary": "Semantic matching",
                    "description": "Match tools using semantic similarity.",
                    "category": "galaxy",
                    "value": {
                        "type": "semantic",
                        "query": "software for molecular docking of proteins",
                        "limit": 10,
                    },
                },
                "dataset": {
                    "summary": "Dataset matching",
                    "description": "Match tool with a dataset description",
                    "category": "galaxy",
                    "value": {
                        "type": "dataset",
                        "description": "Different amino acids (AAs) may exert distinct effects on postprandial glucose and insulin concentrations. A quantitative comparison of the effects of AAs on glucose and insulin kinetics in humans is currently lacking. PubMed was queried to identify intervention studies reporting glucose and insulin concentrations after acute ingestion and/or intravenous infusion of AAs in healthy adults and those living with obesity and/or type 2 diabetes (T2DM). The systematic literature search identified 55 studies that examined the effects of L-leucine, L-isoleucine, L-alanine, L-glutamine, L-arginine, L-lysine, glycine, L-proline, L-phenylalanine, L-glutamate, branched-chain AAs (i.e., L-leucine, L-isoleucine, and L-valine), and multiple individual L-AAs on glucose and insulin concentrations. Oral ingestion of most individual AAs induced an insulin response but did not alter glucose concentrations in healthy participants. Specific AAs (i.e., leucine and isoleucine) co-ingested with glucose exerted a synergistic effect on the postprandial insulin response and attenuated the glucose response compared to glucose intake alone in healthy participants. Oral AA ingestion as well as intravenous AA infusion was able to stimulate an insulin response and decrease glucose concentrations in T2DM and obese individuals. The extracted information is publicly available and can serve multiple purposes such as computational modeling.",
                        "limit": 5,
                    },
                },
            },
        ),
    ],
    db: AsyncSession = Depends(get_db),
) -> list[ToolOutMin]:
    logger.debug(f"Received tool match request with body: {match}")
    match match.type:
        case "file":
            tools = await match_tools_by_file(match, db)
        case "semantic":
            tools = await match_tools_semantically(match, db)
        case "dataset":
            tools = await match_tools_by_dataset_description(match, db)

    # return [ToolOutMin.model_validate(tool) for tool in tools]
    return [
        ToolOutMin.model_validate(
            tool,
            context={"types": extract_all_types(tool)},
        )
        for tool in tools
    ]
