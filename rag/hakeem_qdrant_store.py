import asyncio
import logging
from typing import Any, Optional

from rag.schemas import ScoredChunk

logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
    from qdrant_client.http.exceptions import UnexpectedResponse
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    logger.warning("qdrant-client not installed; HakeemQdrantStore disabled")


class HakeemQdrantStore:
    def __init__(self, host: str = "localhost", port: int = 6333,
                 api_key: str = "", prefix: str = "hakeem",
                 vector_size: int = 384):
        self._host = host
        self._port = port
        self._api_key = api_key
        self._prefix = prefix
        self._vector_size = vector_size
        self._client: Optional[QdrantClient] = None
        self._collections: set[str] = set()

    async def initialize(self, domains: list[str]):
        if not QDRANT_AVAILABLE:
            raise RuntimeError("qdrant-client not installed")

        loop = asyncio.get_event_loop()

        def _init():
            self._client = QdrantClient(
                host=self._host,
                port=self._port,
                api_key=self._api_key or None,
                prefer_grpc=True,
            )
            for domain in domains:
                self._ensure_collection(domain)

        await loop.run_in_executor(None, _init)
        logger.info("HakeemQdrantStore initialized: %d collections, host=%s:%d",
                    len(self._collections), self._host, self._port)

    def _ensure_collection(self, domain: str):
        if not self._client:
            return
        collection_name = f"{self._prefix}_{domain}"

        try:
            existing = self._client.get_collection(collection_name)
            self._collections.add(domain)
            logger.debug("Collection %s already exists", collection_name)
            return
        except (UnexpectedResponse, ValueError):
            pass

        self._client.create_collection(
            collection_name=collection_name,
            vectors_config=qmodels.VectorParams(
                size=self._vector_size,
                distance=qmodels.Distance.COSINE,
                on_disk=False,
            ),
            sparse_vectors_config={
                "bm25": qmodels.SparseVectorParams(
                    index=qmodels.SparseIndexParams(
                        full_scan_threshold=10000,
                    ),
                ),
            },
            optimizers_config=qmodels.OptimizersConfigDiff(
                indexing_threshold=20000,
            ),
        )

        self._client.create_payload_index(
            collection_name=collection_name,
            field_name="domain",
            field_type=qmodels.PayloadSchemaType.KEYWORD,
        )
        self._client.create_payload_index(
            collection_name=collection_name,
            field_name="doc_id",
            field_type=qmodels.PayloadSchemaType.KEYWORD,
        )
        self._client.create_payload_index(
            collection_name=collection_name,
            field_name="parent_chunk_id",
            field_type=qmodels.PayloadSchemaType.KEYWORD,
        )

        self._collections.add(domain)
        logger.info("Created collection %s (domain=%s, vector_size=%d)",
                     collection_name, domain, self._vector_size)

    def _collection_name(self, domain: str) -> str:
        return f"{self._prefix}_{domain}"

    async def add_chunks(self, domain: str, chunks: list[dict[str, Any]],
                         embeddings: list[list[float]]):
        if not self._client:
            raise RuntimeError("QdrantStore not initialized")

        loop = asyncio.get_event_loop()
        collection_name = self._collection_name(domain)

        def _add():
            points = []
            for i, chunk in enumerate(chunks):
                point_id = chunk.get("chunk_id", f"{domain}_{i}")
                points.append(qmodels.PointStruct(
                    id=point_id,
                    vector=embeddings[i] if i < len(embeddings) else [0.0] * self._vector_size,
                    payload={
                        "chunk_id": point_id,
                        "domain": domain,
                        "doc_id": chunk.get("doc_id", ""),
                        "filename": chunk.get("filename", ""),
                        "source_file": chunk.get("source_file", ""),
                        "parent_chunk_id": chunk.get("parent_chunk_id", ""),
                        "parent_text": chunk.get("parent_text", ""),
                        "chunk_index": chunk.get("chunk_index", 0),
                        "content": chunk.get("content", ""),
                        "mtime": chunk.get("mtime", 0),
                    },
                ))

            self._client.upsert(
                collection_name=collection_name,
                points=points,
                wait=True,
            )

        await loop.run_in_executor(None, _add)

    async def hybrid_search(self, domain: str, dense_vector: list[float],
                            sparse_vector: Optional[dict[str, list]],
                            top_k: int = 30) -> list[ScoredChunk]:
        if not self._client:
            return []

        loop = asyncio.get_event_loop()
        collection_name = self._collection_name(domain)

        def _search() -> list[ScoredChunk]:
            prefetch = [
                qmodels.Prefetch(
                    query=dense_vector,
                    limit=top_k,
                ),
            ]
            if sparse_vector:
                prefetch.append(qmodels.Prefetch(
                    query=qmodels.SparseVector(
                        indices=sparse_vector.get("indices", []),
                        values=sparse_vector.get("values", []),
                    ),
                    using="bm25",
                    limit=top_k,
                ))

            results = self._client.query_points(
                collection_name=collection_name,
                prefetch=prefetch,
                query=qmodels.Fusion(
                    fusion=qmodels.FusionQuery.RRF,
                ),
                limit=top_k,
                with_payload=True,
            )

            scored = []
            for point in results.points:
                payload = point.payload or {}
                scored.append(ScoredChunk(
                    chunk_id=payload.get("chunk_id", point.id),
                    content=payload.get("content", ""),
                    score=point.score or 0.0,
                    source_file=payload.get("source_file", ""),
                    filename=payload.get("filename", ""),
                    domain=payload.get("domain", domain),
                    doc_id=payload.get("doc_id", ""),
                    parent_chunk_id=payload.get("parent_chunk_id", ""),
                    parent_text=payload.get("parent_text", ""),
                    chunk_index=payload.get("chunk_index", 0),
                ))
            return scored

        return await loop.run_in_executor(None, _search)

    async def delete_document(self, domain: str, doc_id: str) -> bool:
        if not self._client:
            return False

        loop = asyncio.get_event_loop()
        collection_name = self._collection_name(domain)

        def _delete():
            result = self._client.delete(
                collection_name=collection_name,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="doc_id",
                                match=qmodels.MatchValue(value=doc_id),
                            ),
                        ],
                    ),
                ),
                wait=True,
            )
            return result.status == "completed"

        return await loop.run_in_executor(None, _delete)

    async def list_documents(self, domain: str) -> list[dict[str, Any]]:
        if not self._client:
            return []

        loop = asyncio.get_event_loop()
        collection_name = self._collection_name(domain)

        def _list():
            scroll_result = self._client.scroll(
                collection_name=collection_name,
                limit=10000,
                with_payload=True,
            )
            seen: dict[str, dict] = {}
            for point in scroll_result[0]:
                payload = point.payload or {}
                did = payload.get("doc_id", "")
                if did and did not in seen:
                    seen[did] = {
                        "id": did,
                        "filename": payload.get("filename", ""),
                        "domain": domain,
                        "chunks": 1,
                    }
                elif did:
                    seen[did]["chunks"] += 1
            return list(seen.values())

        return await loop.run_in_executor(None, _list)

    async def collection_count(self, domain: str) -> int:
        if not self._client:
            return 0
        collection_name = self._collection_name(domain)
        try:
            info = self._client.get_collection(collection_name)
            return info.points_count or 0
        except Exception:
            return 0
