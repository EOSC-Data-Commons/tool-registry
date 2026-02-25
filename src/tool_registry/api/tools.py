import logging
from pydantic import BaseModel
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Request, Response
from urllib.parse import unquote
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists, func, literal_column
from sqlalchemy import any_
import httpx
import rdflib

from toolmeta_harvester.db.models import GalaxyWorkflowArtifact
from tool_registry.db import get_db
from tool_registry.security import validate_token
from tool_registry.config import load_oxigraph_config


logger = logging.getLogger(__name__)
router = APIRouter()
config = load_oxigraph_config()


TOOLS_GRAPH = config.name
OXIGRAPH = f"http://{config.host}:{config.port}"


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


@router.post("/", description="Create a new tool by uploading a json-ld or turtle description.", tags=["Tools"])
async def add_tool(request: Request, user_info=Depends(validate_token)):
    content_type = request.headers.get("Content-Type", "")
    logger.debug(f"Received request to add tool with content type: {content_type}")
    if content_type not in ["application/ld+json", "text/turtle"]:
        raise HTTPException(
            status_code=415,
            detail="Unsupported content type. Please use application/ld+json or text/turtle.",
        )
    raw_body = await request.body()
    # Convert JSON-LD → Turtle if needed
    if content_type == "application/ld+json":
        try:
            g = rdflib.Graph()
            g.parse(data=raw_body, format="json-ld")
            turtle_data = g.serialize(format="turtle")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON-LD: {e}")
    else:
        turtle_data = raw_body

    async with httpx.AsyncClient() as client:
        logger.debug(f"Storing tool in Oxigraph graph '{TOOLS_GRAPH}' at {OXIGRAPH}/store")
        logger.debug(turtle_data)
        response = await client.post(
            f"{OXIGRAPH}/store",
            params={"graph": TOOLS_GRAPH},
            content=turtle_data,
            headers={"Content-Type": "text/turtle"},
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text,
        )

    return {"status": "tool stored", "graph": TOOLS_GRAPH}

@router.get("/search")
async def search_tools(fileExtension: str = Query(...)):
    sparql = f"""
    PREFIX tool:   <https://eosc-data-commons.github.io/toolmeta-vocab/toolmeta#>
    PREFIX schema: <https://schema.org/>

    SELECT DISTINCT ?tool ?name
    WHERE {{
      GRAPH <{TOOLS_GRAPH}> {{
        ?tool a schema:SoftwareApplication ;
              tool:hasInterface ?iface .

        ?iface tool:hasInput ?input .
        ?input tool:fileExtension ?ext .

        FILTER(LCASE(?ext) = LCASE("{fileExtension}"))

        OPTIONAL {{ ?tool schema:name ?name }}
      }}
    }}
    """

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OXIGRAPH}/query",
            content=sparql,
            headers={"Content-Type": "application/sparql-query"},
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=500, detail=response.text)

    return response.json()

@router.get("/{tool_id:path}", description="Retrieve a single tool by its identifier.", tags=["Tools"])
async def get_Tool(tool_id: str):
    tool_iri = unquote(tool_id)
    logger.info(f"Retrieving tool with IRI: {tool_iri}")

    if not tool_iri.startswith("http"):
        raise HTTPException(status_code=400, detail="Tool ID must be full IRI")

    sparql = f"""
    PREFIX tool:   <https://eosc-data-commons.github.io/toolmeta-vocab/toolmeta#>
    PREFIX schema: <https://schema.org/>

    CONSTRUCT {{
      ?tool a schema:SoftwareApplication, ?toolType ;
            schema:name ?name ;
            tool:hasInterface ?iface .

      ?iface tool:interfaceVersion ?ifaceVersion ;
             tool:hasInput ?input ;
             tool:hasOutput ?output .

      ?input tool:fileExtension ?inExt ;
             tool:inputType ?inType .

      ?output tool:fileExtension ?outExt ;
              tool:inputType ?outType .
    }}
    WHERE {{
        VALUES ?tool {{ <{tool_iri}> }}
        OPTIONAL {{ ?tool schema:name ?name }}

        OPTIONAL {{
            ?tool a ?toolType .
            FILTER(?toolType != schema:SoftwareApplication)
        }}

        OPTIONAL {{
            ?tool tool:hasInterface ?iface .
            OPTIONAL {{ ?iface tool:interfaceVersion ?ifaceVersion }}

            OPTIONAL {{
            ?iface tool:hasInput ?input .
            OPTIONAL {{ ?input tool:fileExtension ?inExt }}
            OPTIONAL {{ ?input tool:inputType ?inType }}
            }}

            OPTIONAL {{
            ?iface tool:hasOutput ?output .
            OPTIONAL {{ ?output tool:fileExtension ?outExt }}
            OPTIONAL {{ ?output tool:inputType ?outType }}
            }}
        }}
    }}
    """
    logger.debug(f"Executing SPARQL: {sparql}")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OXIGRAPH}/query",
            params={"default-graph-uri": TOOLS_GRAPH},
            content=sparql,
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/n-triples"
            },
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=500, detail=response.text)

    # Parse and re-serialize with prefixes
    g = rdflib.Graph()
    g.parse(data=response.text, format="nt")

    if len(g) == 0:
        raise HTTPException(status_code=404, detail="Tool not found")

    # Compact context
    context = {
        "tool": "https://eosc-data-commons.github.io/toolmeta-vocab/toolmeta#",
        "schema": "https://schema.org/",
        "name": "schema:name",
        "hasInterface": "tool:hasInterface",
        "hasInput": "tool:hasInput",
        "hasOutput": "tool:hasOutput",
        "fileExtension": "tool:fileExtension",
        "inputType": {"@id": "tool:inputType", "@type": "@id"},
        "interfaceVersion": "tool:interfaceVersion",
        "@vocab": "https://schema.org/"
    }

    # g.bind("tool", "https://eosc-data-commons.github.io/toolmeta-vocab/toolmeta#")
    # g.bind("schema", "https://schema.org/")
    #
    # turtle = g.serialize(format="ld+json")

    jsonld = g.serialize(
        format="json-ld",
        context=context,
        indent=2
    )

    return Response(content=jsonld, media_type="application/ld+json")

@router.get("/", description="List all tools in the registry.", tags=["Tools"])
async def list_tools():
    sparql = """
    PREFIX schema: <https://schema.org/>

    SELECT DISTINCT ?tool ?name
    WHERE {
        ?tool a schema:SoftwareApplication .
        OPTIONAL { ?tool schema:name ?name }
    }
    ORDER BY ?name
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OXIGRAPH}/query",
            params={"default-graph-uri": TOOLS_GRAPH},
            content=sparql,
            headers={"Content-Type": "application/sparql-query"},
        )

    return response.json()
# async def list_tools():
#     sparql = """
#         PREFIX tool:   <https://eosc-data-commons.github.io/toolmeta-vocab/toolmeta#>
#         PREFIX schema: <https://schema.org/>
#
#         CONSTRUCT {
#         ?tool a schema:SoftwareApplication ;
#                 schema:name ?name ;
#                 tool:hasInterface ?iface ;
#                 a ?toolType .
#
#         ?iface tool:interfaceVersion ?ifaceVersion ;
#                 tool:hasInput ?input ;
#                 tool:hasOutput ?output .
#
#         ?input tool:fileExtension ?inExt ;
#                 tool:inputType ?inType .
#
#         ?output tool:fileExtension ?outExt ;
#                 tool:inputType ?outType .
#         }
#         WHERE {
#
#         ?tool a schema:SoftwareApplication .
#
#         OPTIONAL { ?tool schema:name ?name }
#
#         OPTIONAL {
#             ?tool a ?toolType .
#             FILTER(?toolType != schema:SoftwareApplication)
#         }
#
#         OPTIONAL {
#             ?tool tool:hasInterface ?iface .
#             OPTIONAL { ?iface tool:interfaceVersion ?ifaceVersion }
#
#             OPTIONAL {
#             ?iface tool:hasInput ?input .
#             OPTIONAL { ?input tool:fileExtension ?inExt }
#             OPTIONAL { ?input tool:inputType ?inType }
#             }
#
#             OPTIONAL {
#             ?iface tool:hasOutput ?output .
#             OPTIONAL { ?output tool:fileExtension ?outExt }
#             OPTIONAL { ?output tool:inputType ?outType }
#             }
#         }
#         }
#     """
#     async with httpx.AsyncClient() as client:
#         response = await client.post(
#             f"{OXIGRAPH}/query",
#             params={"default-graph-uri": TOOLS_GRAPH},
#             content=sparql,
#             headers={"Content-Type": "application/sparql-query",
#                      "Accept": "text/turtle"},
#         )
#
#     if response.status_code >= 400:
#         raise HTTPException(status_code=500, detail=response.text)
#
#     g = rdflib.Graph()
#     g.parse(data=response.text, format="turtle")
#     g.bind("schema", "https://schema.org/")
#     g.bind("eosc:dc", "https://eosc-data-commons.github.io/toolmeta-vocab/toolmeta#")
#
#     turtle_data = g.serialize(format="turtle")
#
#     return Response(
#             content=turtle_data,
#             media_type="text/turtle",
#         )
#

# @router.get(
#     "/",
#     response_model=list[ToolOut],
#     tags=["Tools"],
#     description="Search for tools given query parameters.",
# )
# async def search_tools(
#     name: Optional[str] = Query(
#         None,
#         description="Partial match for tool name.",
#         example="genomic",
#     ),
#     input_format: Optional[str] = Query(
#         None,
#         description="Filter tools by input format.",
#         example="fasta",
#     ),
#     output_format: Optional[str] = Query(
#         None,
#         description="Filter tools by output format.",
#         example="cram",
#     ),
#     tag: Optional[str] = Query(
#         None,
#         description="Filter tools by tag.",
#         example="covid",
#     ),
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     Search for tools based on provided criteria.
#     """
#     search = ToolSearchParams(
#         name=name,
#         input_format=input_format,
#         output_format=output_format,
#         tag=tag,
#     )
#     tools = await search_galaxy_tools(search, db)
#     logger.debug(f"Found {len(tools)} tools matching search criteria.")
#     return [ToolOut.from_orm(tool) for tool in tools]
#
#
# @router.get(
#     "/{identifier}",
#     response_model=ToolOut,
#     description="Retrieve a single tool by uuid.",
#     tags=["Tools"],
# )
# async def get_tools_by_identifier(
#     identifier: str = Path(
#         ...,
#         description="The UUID of the tool to retrieve.",
#         example="123e4567-e89b-12d3-a456-426614174000",
#     ),
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     Retrieve a single tool by its UUID.
#     """
#     tool = await get_galaxy_tool_by_uuid(identifier, db)
#     if not tool:
#         raise HTTPException(status_code=404, detail="Tool not found")
#     logger.debug(f"Retrieved tool: {tool.name} (UUID: {tool.uuid})")
#     return ToolOut.from_orm(tool)
