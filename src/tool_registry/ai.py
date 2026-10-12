import httpx
import json

EGI_CHAT_API = "https://llm.ai.egi.eu/chat/completions"
LLM_MODEL = "qwen3.5"

SYSTEM_PROMPT = """
You are a scientific software discovery assistant.

Given a scientific dataset description, generate semantic search
queries to discover scientific software tools that could analyse,
process, model, or visualise the dataset.

Instructions:
- Identify distinct computational tasks relevant to the dataset.
- Generate one query per distinct task.
- Generate between 1 and 5 queries.
- Avoid redundant or overlapping queries.
- Describe software capabilities, not dataset findings.
- Use terminology common in scientific software descriptions.
- Preserve relevant scientific domain terminology.
- Do not invent data formats or unsupported data characteristics.
- Do not name specific software packages.
- Each query should be 20-50 words.

Return valid JSON only, with this structure:

{
    "queries": [
        {
            "intent": "short descriptive name",
            "query": "semantic search query"
        }
    ]
}
"""

PROMPT_VERSION = "v2"


async def dataset_to_tool_queries(
    description: str,
    api_key: str,
) -> list[dict]:

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            EGI_CHAT_API,
            headers={
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": description},
                ],
                "temperature": 0,
            },
        )

        response.raise_for_status()

        result = json.loads(response.json()["choices"][0]["message"]["content"])

        queries = result["queries"]

        if not isinstance(queries, list) or not all(
            isinstance(item, dict)
            and isinstance(item.get("intent"), str)
            and isinstance(item.get("query"), str)
            for item in queries
        ):
            raise ValueError("Invalid LLM query response")

        queries = queries[:5]
        if not queries:
            raise ValueError("LLM returned no queries")

        return queries
