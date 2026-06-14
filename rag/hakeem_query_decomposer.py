import asyncio
import json
import logging
from typing import Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_DECOMPOSITION_PROMPT = (
    "You are a medical query decomposition assistant. "
    "Break the following clinical question into {num} simpler sub-questions "
    "that each target a distinct aspect of the original question. "
    "Return the sub-questions as a JSON array of strings, nothing else.\n\n"
    "Question: {query}"
)


class HakeemQueryDecomposer:
    def __init__(self, api_base: str, model: str,
                 api_key: str = "", num_queries: int = 3):
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_base,
        )
        self._model = model
        self._num_queries = num_queries

    async def decompose(self, query: str,
                        num_queries: Optional[int] = None,
                        api_base: Optional[str] = None,
                        api_key: Optional[str] = None) -> list[str]:
        n = num_queries or self._num_queries
        if n <= 1:
            return [query]

        client = self._client
        if api_base or api_key:
            client = AsyncOpenAI(
                api_key=api_key or "",
                base_url=api_base or self._client.base_url,
            )

        try:
            prompt = _DECOMPOSITION_PROMPT.format(num=n, query=query)
            response = await client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
            )
            content = response.choices[0].message.content or ""

            sub_queries = json.loads(content)
            if isinstance(sub_queries, list) and len(sub_queries) > 0:
                logger.debug("Decomposed query into %d sub-queries", len(sub_queries))
                return sub_queries[:n]

        except Exception as e:
            logger.warning("Query decomposition failed: %s", e)

        return [query]
