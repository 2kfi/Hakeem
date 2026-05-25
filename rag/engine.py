import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Optional

import numpy as np

from core.config import RAGSettings

logger = logging.getLogger(__name__)


_TOKENIZER = None
_ONNX_SESSION = None


def _load_onnx_model(model_dir: str, device: str = "auto"):
    global _TOKENIZER, _ONNX_SESSION
    if _ONNX_SESSION is not None:
        return

    import json
    from tokenizers import Tokenizer

    onnx_path = Path(model_dir) / "onnx"
    model_file = str(onnx_path / "model.onnx")
    tokenizer_file = str(onnx_path / "tokenizer.json")

    if not os.path.exists(model_file):
        raise FileNotFoundError(
            f"ONNX model not found at {model_file}. "
            f"Download it: place onnx.tar.gz in {model_dir} and extract."
        )
    if not os.path.exists(tokenizer_file):
        raise FileNotFoundError(f"Tokenizer not found at {tokenizer_file}")

    import onnxruntime as ort

    so = ort.SessionOptions()
    so.log_severity_level = 3
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    providers = ort.get_available_providers()
    if "CoreMLExecutionProvider" in providers:
        providers.remove("CoreMLExecutionProvider")

    if device == "cpu":
        providers = [p for p in providers if "CUDA" not in p and "TensorRT" not in p]
        logger.info("ONNX providers (CPU-only): %s", providers)
    elif device == "cuda":
        if "CUDAExecutionProvider" in providers:
            providers.remove("CUDAExecutionProvider")
            providers = ["CUDAExecutionProvider"] + providers
            logger.info("ONNX providers (CUDA preferred): %s", providers)

    _ONNX_SESSION = ort.InferenceSession(model_file, providers=providers, sess_options=so)

    _TOKENIZER = Tokenizer.from_file(tokenizer_file)
    _TOKENIZER.enable_truncation(max_length=256)
    _TOKENIZER.enable_padding(pad_id=0, pad_token="[PAD]", length=256)


def _embed(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    if _ONNX_SESSION is None or _TOKENIZER is None:
        raise RuntimeError("ONNX model not loaded")

    all_embeddings: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        encoded = _TOKENIZER.encode_batch(batch)
        input_ids = np.array([b.ids for b in encoded], dtype=np.int64)
        attention_mask = np.array([b.attention_mask for b in encoded], dtype=np.int64)
        token_type_ids = np.array([b.type_ids for b in encoded], dtype=np.int64)

        outs = _ONNX_SESSION.run(
            None,
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids,
            },
        )
        token_emb = outs[0]
        mask = np.expand_dims(attention_mask.astype(np.float32), axis=-1)
        embeddings = np.sum(token_emb * mask, axis=1) / np.maximum(np.sum(mask, axis=1), 1e-9)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        embeddings = embeddings / norms
        all_embeddings.extend(embeddings.tolist())
    return all_embeddings


class TextSplitter:
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> list[str]:
        paragraphs = text.split("\n\n")
        chunks = []
        current = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current) + len(para) < self.chunk_size:
                current = (current + "\n\n" + para).strip()
            else:
                if current:
                    chunks.append(current)
                current = para
        if current:
            chunks.append(current)

        if self.chunk_overlap > 0 and len(chunks) > 1:
            overlapped = []
            for i, c in enumerate(chunks):
                overlapped.append(c)
                if i < len(chunks) - 1:
                    prev_words = c.split()
                    overlap_words = prev_words[-min(self.chunk_overlap, len(prev_words)):]
                    if overlap_words:
                        next_first = chunks[i + 1].split()[:min(20, len(chunks[i + 1].split()))]
                        overlapped.append(" ".join(overlap_words) + "\n" + " ".join(next_first))
            chunks = overlapped

        return [c.strip() for c in chunks if c.strip()]


class RAGEngine:
    def __init__(self, settings: RAGSettings):
        self._settings = settings
        self._chroma_client: Any = None
        self._collection: Any = None
        self._splitter = TextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def collection_count(self) -> int:
        if not self._initialized or self._collection is None:
            return 0
        return self._collection.count()

    async def initialize(self) -> None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        loop = asyncio.get_event_loop()

        def _init():
            os.makedirs(self._settings.vector_store_path, exist_ok=True)

            model_dir = self._settings.model_dir
            _load_onnx_model(model_dir, device=self._settings.device)

            self._chroma_client = chromadb.PersistentClient(
                path=self._settings.vector_store_path,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._chroma_client.get_or_create_collection(
                name="hakeem_rag",
                metadata={"hnsw:space": "cosine"},
            )

        await loop.run_in_executor(None, _init)
        self._initialized = True
        logger.info(
            f"RAGEngine initialized: model_dir={self._settings.model_dir}/onnx, "
            f"collection={self._collection.count()} chunks"
        )

    async def index_document(self, file_path: str, doc_id: Optional[str] = None) -> dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("RAGEngine not initialized")

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        doc_id = doc_id or path.stem
        text = path.read_text(encoding="utf-8", errors="replace")

        if not text.strip():
            logger.warning(f"Empty file: {file_path}")
            return {"doc_id": doc_id, "filename": path.name, "chunks": 0, "status": "empty"}

        loop = asyncio.get_event_loop()

        file_mtime = path.stat().st_mtime

        def _index():
            chunks = self._splitter.split_text(text)
            embeddings = _embed(chunks, batch_size=self._settings.indexing_batch_size)
            ids = [f"{doc_id}:chunk:{i}" for i in range(len(chunks))]
            metadatas = [
                {
                    "doc_id": doc_id,
                    "filename": path.name,
                    "source_file": str(path),
                    "chunk_index": i,
                    "mtime": file_mtime,
                }
                for i in range(len(chunks))
            ]

            existing = self._collection.get(where={"doc_id": doc_id})
            if existing["ids"]:
                self._collection.delete(ids=existing["ids"])

            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=chunks,
            )
            return len(chunks)

        chunk_count = await loop.run_in_executor(None, _index)
        logger.info(f"Indexed {path.name}: {chunk_count} chunks")
        return {"doc_id": doc_id, "filename": path.name, "chunks": chunk_count, "status": "indexed"}

    async def index_directory(self, directory: str) -> list[dict[str, Any]]:
        if not self._initialized:
            raise RuntimeError("RAGEngine not initialized")

        path = Path(directory)
        if not path.exists():
            logger.warning(f"Directory not found: {directory}")
            return []

        results = []
        supported = {".md", ".txt", ".yaml", ".yml", ".json"}
        for f in sorted(path.rglob("*")):
            if f.is_file() and f.suffix.lower() in supported:
                try:
                    result = await self.index_document(str(f))
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to index {f}: {e}")
        logger.info(f"Indexed {len(results)} files from {directory}")
        return results

    async def index_if_changed(self, dirs: list[str]) -> int:
        if not self._initialized:
            return 0

        loop = asyncio.get_event_loop()

        def _get_existing():
            all_data = self._collection.get(include=["metadatas"])
            doc_mtimes: dict[str, float | None] = {}
            for i, chunk_id in enumerate(all_data["ids"]):
                meta = all_data["metadatas"][i] if all_data["metadatas"] else {}
                did = meta.get("doc_id", chunk_id)
                if did not in doc_mtimes:
                    doc_mtimes[did] = meta.get("mtime")
            return doc_mtimes

        existing_mtimes = await loop.run_in_executor(None, _get_existing)

        supported = {".md", ".txt", ".yaml", ".yml", ".json"}
        total_chunks = 0

        for d in dirs:
            dpath = Path(d)
            if not dpath.exists():
                logger.warning(f"RAG: source directory not found: {d}")
                continue

            for f in sorted(dpath.rglob("*")):
                if not f.is_file() or f.suffix.lower() not in supported:
                    continue

                doc_id = f.stem
                current_mtime = f.stat().st_mtime
                stored_mtime = existing_mtimes.get(doc_id)
                rel = str(f.resolve().relative_to(Path.cwd().resolve()))

                if doc_id not in existing_mtimes:
                    logger.info(f"RAG: {rel}: NEW → indexing")
                elif stored_mtime is None or current_mtime > stored_mtime:
                    if stored_mtime is None:
                        logger.info(f"RAG: {rel}: no stored mtime → re-indexing")
                    else:
                        logger.info(
                            f"RAG: {rel}: mtime CHANGED "
                            f"({stored_mtime} → {current_mtime}) → re-indexing"
                        )
                else:
                    logger.debug(f"RAG: {rel}: unchanged → skipping")
                    continue

                result = await self.index_document(str(f), doc_id=doc_id)
                total_chunks += result.get("chunks", 0)
                delay = self._settings.indexing_delay_ms / 1000
                if delay > 0:
                    await asyncio.sleep(delay)

        logger.info(f"RAG: index_if_changed done, {total_chunks} chunks indexed")
        return total_chunks

    async def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
    ) -> list[dict[str, Any]]:
        if not self._initialized:
            return []

        top_k = top_k or self._settings.top_k
        min_score = min_score or self._settings.min_score

        loop = asyncio.get_event_loop()

        def _search():
            q_emb = _embed([query])[0]
            results = self._collection.query(
                query_embeddings=[q_emb],
                n_results=top_k,
            )
            return results

        raw = await loop.run_in_executor(None, _search)
        if not raw["ids"] or not raw["ids"][0]:
            return []

        output = []
        for i, chunk_id in enumerate(raw["ids"][0]):
            distance = raw["distances"][0][i] if raw["distances"] else 0.0
            similarity = 1.0 - (distance ** 2) / 2.0
            if similarity < min_score:
                continue
            meta = raw["metadatas"][0][i] if raw["metadatas"] else {}
            output.append({
                "chunk_id": chunk_id,
                "content": raw["documents"][0][i],
                "score": similarity,
                "source_file": meta.get("source_file", ""),
                "filename": meta.get("filename", ""),
            })
        return output

    def format_context(self, results: list[dict[str, Any]]) -> str:
        if not results:
            return ""
        sections = []
        for r in results:
            src = r.get("source_file", "unknown")
            sections.append(f"[Source: {src}]\n{r.get('content', '')}")
        return "\n\n---\n\n".join(sections)

    async def delete_document(self, doc_id: str) -> bool:
        if not self._initialized:
            return False

        loop = asyncio.get_event_loop()

        def _delete():
            existing = self._collection.get(where={"doc_id": doc_id})
            if existing["ids"]:
                self._collection.delete(ids=existing["ids"])
                return True
            return False

        return await loop.run_in_executor(None, _delete)

    async def list_documents(self) -> list[dict[str, Any]]:
        if not self._initialized:
            return []

        loop = asyncio.get_event_loop()

        def _list():
            all_data = self._collection.get(include=["metadatas"])
            seen = {}
            for i, doc_id in enumerate(all_data["ids"]):
                meta = all_data["metadatas"][i] if all_data["metadatas"] else {}
                did = meta.get("doc_id", doc_id)
                if did not in seen:
                    seen[did] = {"id": did, "filename": meta.get("filename", ""), "chunks": 0}
                seen[did]["chunks"] += 1
            return list(seen.values())

        return await loop.run_in_executor(None, _list)


_engine: Optional[RAGEngine] = None


async def get_rag_engine() -> Optional[RAGEngine]:
    return _engine


async def init_rag_engine(settings: RAGSettings) -> Optional[RAGEngine]:
    global _engine
    if not settings.enabled:
        logger.info("RAG is disabled (RAG_ENABLED=false)")
        return None
    engine = RAGEngine(settings)
    await engine.initialize()
    _engine = engine
    return engine
