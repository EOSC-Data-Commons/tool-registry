import httpx

EGI_CHAT_API = "https://llm.ai.egi.eu/chat/completions"
LLM_MODEL = "qwen3.5"

SYSTEM_PROMPT = """
You are a scientific software discovery assistant.

Translate a scientific dataset description into a semantic search
query for finding software tools that can analyse, process, model,
or visualise the dataset.

Identify:
- Scientific domain
- Data characteristics and measured variables
- Potential computational operations
- Relevant analytical methods

Rules:
- Focus on software capabilities, not research conclusions.
- Use terminology commonly found in scientific tool descriptions.
- Preserve important scientific concepts.
- Do not invent data types, formats, or experimental details.
- Do not name specific software tools.
- Return only a concise search query (40-80 words).
"""

PROMPT_VERSION = "v1"


async def dataset_to_tool_query(
    description: str,
    api_key: str,
) -> str:
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
        data = response.json()

        return data["choices"][0]["message"]["content"].strip()
