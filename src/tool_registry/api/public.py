from typing import Any, Optional, Iterator
from fastapi import APIRouter, Request
from pathlib import Path
import json

router = APIRouter()


# Returns a list of all supported tools (each item contains `toolURI`, `toolLabel`, `toolDescription`).
@router.get("/", description="List all supported tools. Each item contains 'toolURI', 'toolLabel', and 'toolDescription'.")

# Returns a single tool matching `identifier
# Supports:
#  - `edc:fil.<...>` -> match by file type (`typeURI`)
#  - `edc:tool.<...>` -> match by tool URI (`toolURI`)
@router.get("/{identifier}", description="Retrieve a single tool matching the provided filter. Supports 'edc:fil.*' (typeURI) and 'edc:tool.*' (toolURI).")
async def get_tools_by_identifier(request: Request, identifier: Optional[str] = None):
    """
    Handle GET requests to retrieve tools or identifier them based on a specific URI.

    This endpoint supports two routes:
    1. `/` - Returns a list of all tools.
    2. `/{identifier}` - Filters tools based on the provided `identifier` parameter.

    Args:
        request (Request): The incoming HTTP request object.
        identifier (Optional[str]): A string used to filter tools. It can start with:
            - "edc:fil." to filter by file type (typeURI).
            - "edc:tool." to filter by tool URI (toolURI).

    Returns:
        list[dict] or dict: A list of all tools if no identifier is provided, or a single
        tool matching the identifier criteria. Returns an empty dictionary if no match is found.
    """
    if not identifier:
        return await get_tools()
    if identifier.startswith("edc:fil."):
        return await find_tool(match_type="typeURI", match_value=identifier)

    if identifier.startswith("edc:tool."):
        return await find_tool(match_type="toolURI", match_value=identifier)
    return {}


async def get_tools() -> list[Any]:
    tools = []
    for data in _iter_tool_data():
        tool_uri = data.get("toolURI")
        props = data.get("toolProperties", {})
        tool_label = props.get("toolLabel") or ""
        tool_description = props.get("toolDescription") or ""
        if tool_uri:
            tools.append({
                "toolURI": tool_uri,
                "toolLabel": tool_label,
                "toolDescription": tool_description
            })
    return tools


async def find_tool(match_type: str, match_value: str) -> dict:
    """
    Generic finder for tools.

    match_type: "toolURI" or "typeURI"
    match_value: value to match (e.g. "edc:tool.443..." or "edc:fil.0CC5...")
    """
    for data in _iter_tool_data():
        if match_type == "toolURI":
            if data.get("toolURI") == match_value:
                props = data.get("toolProperties", {})
                return {
                    "toolURI": match_value,
                    "toolLabel": props.get("toolLabel", ""),
                    "toolDescription": props.get("toolDescription", "")
                }

        elif match_type == "typeURI":
            type_entries = data.get("typeURI", [])
            for entry in type_entries:
                entry_val = entry.get("typeURI") if isinstance(entry, dict) else entry
                if entry_val == match_value:
                    props = data.get("toolProperties", {})
                    return {
                        "typeURI": match_value,
                        "toolLabel": props.get("toolLabel", ""),
                        "toolDescription": props.get("toolDescription", "")
                    }

    return {}


def _get_supported_tools_base() -> Path:
    # lazy import to avoid circular import with `src.main`
    from src.main import app_settings
    base = Path(app_settings.SUPPORTED_TOOLS_DIR)
    print("SUPPORTED_TOOLS_DIR", base)
    return base


def _iter_tool_data() -> Iterator[dict]:
    """Yield parsed JSON dicts for each .json tool file in the supported-tools dir."""
    base = _get_supported_tools_base()
    if not base.exists() or not base.is_dir():
        return
    for path in sorted(base.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        yield data