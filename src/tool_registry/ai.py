import httpx
import re
import logging
import json
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

logger = logging.getLogger(__name__)

EGI_CHAT_API = "https://llm.ai.egi.eu/chat/completions"
# LLM_MODEL = "qwen3.8-27b"
# EXTRA_OPTIONS = {
#     "chat_template_kwargs": {"enable_thinking": False},
# }
LLM_MODEL = "mistral-small-4:119b"
EXTRA_OPTIONS = {}

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
- Each query should be 15-30 words.

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

PROMPT_VERSION = "v3"


# Compresses a text description using TF-IDF-based extractive summarisation.
#
# The function splits the description into sentences and uses scikit-learn's
# TfidfVectorizer to identify distinctive words and two-word phrases (bigrams).
# Common English stop words are excluded, and sublinear term frequency scaling
# reduces the influence of frequently repeated terms.
#
# Each sentence is scored using its highest TF-IDF value, favouring sentences
# containing distinctive terminology. Sentences are then selected in descending
# score order until the maximum word limit is reached.
#
# Finally, the selected sentences are restored to their original order to
# preserve readability and context.
#
# This approach is computationally inexpensive, requires no pretrained models,
# and preserves the original wording. However, it relies on statistical term
# importance rather than semantic understanding, so important contextual
# information may be omitted.
#
# Parameters:
#     description: Original text to compress.
#     max_words: Maximum number of words in the compressed description.
#
# Returns:
#     A shortened description containing the highest-ranked sentences,
#     or the original description if it is already within the word limit.
def compress_description(
    description: str,
    max_words: int = 100,
) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", description.strip())

    if len(description.split()) <= max_words or len(sentences) < 2:
        return description

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
    )

    matrix = vectorizer.fit_transform(sentences)

    # Rank sentences by their highest distinctive term scores.
    scores = np.asarray(matrix.max(axis=1).toarray()).ravel()

    selected = []
    word_count = 0

    for idx in np.argsort(scores)[::-1]:
        sentence = sentences[idx]
        words = len(sentence.split())

        if word_count + words <= max_words:
            selected.append(idx)
            word_count += words

    return " ".join(sentences[i] for i in sorted(selected))


async def dataset_to_tool_queries(
    description: str,
    api_key: str,
) -> list[dict]:

    async with httpx.AsyncClient(timeout=120) as client:
        compressed_description = compress_description(description)
        logger.debug(f"NLP compressed description: {compressed_description}")

        response = await client.post(
            EGI_CHAT_API,
            headers={
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": compressed_description},
                ],
                "temperature": 0,
                **EXTRA_OPTIONS,
            },
        )

        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"].strip()

        # Remove optional Markdown JSON fences
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content)

        result = json.loads(content)

        # result = json.loads(response.json()["choices"][0]["message"]["content"])

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
