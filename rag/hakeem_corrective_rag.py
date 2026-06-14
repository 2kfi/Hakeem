import logging
from typing import Optional

from openai import AsyncOpenAI

from rag.schemas import CRAGResult, ScoredChunk

logger = logging.getLogger(__name__)

_VERIFICATION_PROMPT = (
    "You are a clinical fact-checker. Determine if the provided context "
    "contains sufficient information to answer the user's question. "
    "Respond with exactly one word: YES, NO, or PARTIAL.\n\n"
    "Question: {query}\n\n"
    "Context:\n{context}\n\n"
    "Does the context contain enough information to answer the question?"
)

_ABSTRACTION_MESSAGE = (
    "I cannot verify this answer from the available clinical documentation. "
    "Insufficient clinical data in internal database. "
    "Please consult a qualified medical professional."
)


class HakeemCorrectiveRAG:
    def __init__(self, api_base: str, model: str,
                 api_key: str = "", enabled: bool = True):
        self._client = AsyncOpenAI(api_key=api_key, base_url=api_base)
        self._model = model
        self._enabled = enabled

    async def verify(self, query: str,
                     chunks: list[ScoredChunk]) -> CRAGResult:
        if not self._enabled or not chunks:
            return CRAGResult(sufficient=bool(chunks), status="skipped")

        context = "\n\n---\n\n".join(
            f"[Doc: {c.filename}] {c.content[:2000]}"
            for c in chunks[:5]
        )

        try:
            prompt = _VERIFICATION_PROMPT.format(query=query, context=context)
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=10,
            )
            answer = response.choices[0].message.content.strip().upper()

            if answer == "YES":
                return CRAGResult(sufficient=True, status="sufficient",
                                  score=1.0)
            elif answer == "PARTIAL":
                return CRAGResult(sufficient=True, status="partial",
                                  score=0.6)
            else:
                return CRAGResult(sufficient=False, status="insufficient",
                                  score=0.0, feedback=answer)

        except Exception as e:
            logger.warning("CRAG verification failed: %s", e)
            return CRAGResult(sufficient=True, status="unverifiable",
                              score=0.5)

    async def abstain(self) -> str:
        return _ABSTRACTION_MESSAGE
