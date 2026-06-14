import asyncio
import logging
import math
from collections import defaultdict
from typing import Optional

from rag.hakeem_qdrant_store import HakeemQdrantStore
from rag.schemas import ScoredChunk

logger = logging.getLogger(__name__)


class HakeemHybridRetriever:
    def __init__(self, qdrant_store: HakeemQdrantStore,
                 rrf_k: int = 60, top_k: int = 30):
        self._qdrant = qdrant_store
        self._rrf_k = rrf_k
        self._top_k = top_k

    async def search(self, query: str, domains: list[str],
                     dense_vector: list[float],
                     sparse_vector: Optional[dict] = None,
                     sub_queries: Optional[list[str]] = None,
                     query_embeddings: Optional[list[tuple[str, list[float], dict]]] = None,
                     top_k: Optional[int] = None) -> list[ScoredChunk]:
        k = top_k or self._top_k
        all_result_lists: list[list[ScoredChunk]] = []

        if query_embeddings:
            for sq, dv, sv in query_embeddings:
                for domain in domains:
                    results = await self._qdrant.hybrid_search(
                        domain=domain,
                        dense_vector=dv,
                        sparse_vector=sv,
                        top_k=k,
                    )
                    if results:
                        all_result_lists.append(results)
        else:
            queries_to_run = sub_queries or [query]
            for sq in queries_to_run:
                for domain in domains:
                    results = await self._qdrant.hybrid_search(
                        domain=domain,
                        dense_vector=dense_vector,
                        sparse_vector=sparse_vector,
                        top_k=k,
                    )
                    if results:
                        all_result_lists.append(results)

        if not all_result_lists:
            return []

        fused = self._reciprocal_rank_fusion(all_result_lists)
        return fused[:k]

    def _reciprocal_rank_fusion(self,
                                 result_lists: list[list[ScoredChunk]],
                                 ) -> list[ScoredChunk]:
        scores: dict[str, dict] = {}
        k = self._rrf_k

        for rank_list in result_lists:
            for rank, chunk in enumerate(rank_list):
                doc_id = chunk.parent_chunk_id or chunk.chunk_id
                if doc_id not in scores:
                    scores[doc_id] = {
                        "chunk": chunk,
                        "rrf_score": 0.0,
                        "appearances": 0,
                    }
                scores[doc_id]["rrf_score"] += 1.0 / (k + rank + 1)
                scores[doc_id]["appearances"] += 1

        sorted_docs = sorted(
            scores.values(),
            key=lambda x: (-x["rrf_score"], -x["appearances"]),
        )

        for entry in sorted_docs:
            entry["chunk"].score = entry["rrf_score"]

        return [entry["chunk"] for entry in sorted_docs]
