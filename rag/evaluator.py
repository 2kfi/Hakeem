# Arkan Fakoseh -  @2kfi on github
import logging
from typing import Optional

from llama_index.core.evaluation import FaithfulnessEvaluator
from llama_index.core.evaluation.base import EvaluationResult
from llama_index.llms.openai import OpenAI

logger = logging.getLogger(__name__)


class RagEvaluator:
    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        llm = OpenAI(
            model=model,
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._evaluator = FaithfulnessEvaluator(llm=llm)

    async def evaluate(
        self, response: str, contexts: list[str]
    ) -> EvaluationResult:
        result = await self._evaluator.aevaluate(
            response=response,
            contexts=contexts,
        )
        return result

    async def evaluate_with_retry(
        self,
        query: str,
        response: str,
        contexts: list[str],
        max_attempts: int = 2,
    ) -> tuple[str, EvaluationResult]:
        current_response = response
        final_result: Optional[EvaluationResult] = None

        for attempt in range(max_attempts):
            result = await self.evaluate(
                response=current_response,
                contexts=contexts,
            )
            final_result = result

            if result.passing is not False:
                return current_response, result

            logger.warning(
                f"Faithfulness check failed (attempt {attempt + 1}/{max_attempts}): "
                f"score={result.score:.2f}, feedback={result.feedback}"
            )

            if attempt < max_attempts - 1:
                current_response = (
                    f"Answer the user's question based strictly on the provided context. "
                    f"Do not add information outside the context.\n\n"
                    f"Question: {query}\n\n"
                    f"Context:\n{chr(10).join(contexts)}"
                )

        return current_response, final_result

    async def is_context_sufficient(
        self, query: str, contexts: list[str]
    ) -> bool:
        if not contexts:
            return False

        response = f"The question is: {query}\nBased on the provided context, answer with YES if the context contains enough information to answer the question, or NO if it does not."
        result = await self.evaluate(
            response=response,
            contexts=contexts,
        )
        return result.passing is True
