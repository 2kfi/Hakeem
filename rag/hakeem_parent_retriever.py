import asyncio
import hashlib
import logging
from typing import Any, Optional

from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document as LiDocument

from rag.onnx_embedding import OnnxEmbedding
from rag.schemas import ScoredChunk

logger = logging.getLogger(__name__)


class HakeemParentRetriever:
    def __init__(self, embed_model: OnnxEmbedding,
                 child_chunk_size: int = 128,
                 child_chunk_overlap: int = 16,
                 parent_chunk_size: int = 1024,
                 parent_chunk_overlap: int = 64):
        self._embed_model = embed_model
        self._child_splitter = SentenceSplitter(
            chunk_size=child_chunk_size,
            chunk_overlap=child_chunk_overlap,
        )
        self._parent_splitter = SentenceSplitter(
            chunk_size=parent_chunk_size,
            chunk_overlap=parent_chunk_overlap,
        )

    def chunk_document(self, text: str, doc_id: str, filename: str,
                       source_file: str, domain: str,
                       mtime: float = 0) -> tuple[list[dict[str, Any]],
                                                  list[list[float]]]:
        li_doc = LiDocument(text=text)
        parent_nodes = self._parent_splitter.get_nodes_from_documents([li_doc])
        child_nodes = self._child_splitter.get_nodes_from_documents([li_doc])

        parent_chunks: list[dict[str, Any]] = []
        child_chunks: list[dict[str, Any]] = []

        for i, parent_node in enumerate(parent_nodes):
            parent_id = f"{doc_id}_parent_{i}"
            parent_text = parent_node.get_content()
            parent_chunks.append({
                "chunk_id": parent_id,
                "doc_id": doc_id,
                "filename": filename,
                "source_file": source_file,
                "domain": domain,
                "mtime": mtime,
                "content": parent_text,
                "parent_chunk_id": parent_id,
                "parent_text": parent_text,
                "chunk_index": i,
                "is_parent": True,
            })

        for i, child_node in enumerate(child_nodes):
            child_text = child_node.get_content()
            parent_id = self._find_parent_id(child_text, parent_chunks)
            child_chunks.append({
                "chunk_id": f"{doc_id}_child_{i}",
                "doc_id": doc_id,
                "filename": filename,
                "source_file": source_file,
                "domain": domain,
                "mtime": mtime,
                "content": child_text,
                "parent_chunk_id": parent_id or parent_chunks[0]["chunk_id"],
                "parent_text": next(
                    (p["parent_text"] for p in parent_chunks
                     if p["chunk_id"] == parent_id),
                    parent_chunks[0]["parent_text"] if parent_chunks else child_text,
                ),
                "chunk_index": i,
                "is_parent": False,
            })

        child_embeddings = self._embed_texts([c["content"] for c in child_chunks])

        logger.debug("Chunked %s: %d parents, %d children",
                     filename, len(parent_chunks), len(child_chunks))

        return child_chunks, child_embeddings

    def resolve_parents(self, chunks: list[ScoredChunk]) -> list[ScoredChunk]:
        parent_map: dict[str, ScoredChunk] = {}

        for chunk in chunks:
            parent_id = chunk.parent_chunk_id or chunk.chunk_id
            if parent_id not in parent_map:
                parent_map[parent_id] = ScoredChunk(
                    chunk_id=parent_id,
                    content=chunk.parent_text or chunk.content,
                    score=chunk.score,
                    source_file=chunk.source_file,
                    filename=chunk.filename,
                    domain=chunk.domain,
                    doc_id=chunk.doc_id,
                    parent_chunk_id=parent_id,
                    parent_text=chunk.parent_text or chunk.content,
                    chunk_index=chunk.chunk_index,
                )
            else:
                existing = parent_map[parent_id]
                existing.score = max(existing.score, chunk.score)

        return list(parent_map.values())

    def _find_parent_id(self, child_text: str,
                        parent_chunks: list[dict]) -> Optional[str]:
        child_words = set(child_text.lower().split())
        best_parent = None
        best_overlap = 0

        for p in parent_chunks:
            parent_words = set(p["content"].lower().split())
            overlap = len(child_words & parent_words)
            if overlap > best_overlap:
                best_overlap = overlap
                best_parent = p["chunk_id"]

        return best_parent

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self._embed_model._get_text_embeddings(texts)
