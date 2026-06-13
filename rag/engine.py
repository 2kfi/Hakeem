# Arkan Fakoseh -  @2kfi on github
import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from llama_index.core import VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document, NodeRelationship, RelatedNodeInfo, ObjectType
from llama_index.vector_stores.chroma import ChromaVectorStore

from core.config import RAGSettings
from rag.download import download_onnx_model
from rag.onnx_embedding import OnnxEmbedding, _load_onnx_session

logger = logging.getLogger(__name__)


_SUPPORTED_EXTENSIONS = {
    ".md", ".txt", ".yaml", ".yml", ".json",
    ".pdf", ".docx", ".odt", ".odp", ".ods",
    ".csv", ".xlsx", ".xls", ".pptx",
    ".html", ".htm", ".zim",
}


def _read_file(path: Path) -> str:
    ext = path.suffix.lower()

    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)

    if ext == ".docx":
        from docx import Document as DocxDocument
        doc = DocxDocument(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)

    if ext in (".odt", ".odp", ".ods"):
        from odf import text, teletype
        from odf.opendocument import load
        doc = load(str(path))
        paragraphs = doc.getElementsByType(text.P)
        lines = [teletype.extractText(p) for p in paragraphs if teletype.extractText(p)]
        return "\n\n".join(lines)

    if ext == ".csv":
        import csv, io
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            rows = list(csv.reader(f))
        if not rows:
            return ""
        header = " | ".join(rows[0])
        data = "\n".join(" | ".join(row) for row in rows[1:])
        return f"{header}\n{data}"

    if ext in (".xlsx", ".xls"):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        parts = []
        for sheet in wb.sheetnames:
            ws = wb[sheet]
            rows = []
            for row in ws.iter_rows(values_only=True):
                cleaned = [str(c) if c is not None else "" for c in row]
                rows.append(" | ".join(cleaned))
            if rows:
                parts.append(f"[Sheet: {sheet}]\n" + "\n".join(rows))
        wb.close()
        return "\n\n".join(parts)

    if ext == ".pptx":
        from pptx import Presentation
        prs = Presentation(str(path))
        slides = []
        for slide_num, slide in enumerate(prs.slides, 1):
            texts = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        t = para.text.strip()
                        if t:
                            texts.append(t)
                if shape.has_table:
                    table = shape.table
                    for row in table.rows:
                        cells = [cell.text.strip() for cell in row.cells]
                        texts.append(" | ".join(cells))
            if texts:
                slides.append(f"[Slide {slide_num}]\n" + "\n".join(texts))
        return "\n\n".join(slides)

    if ext in (".html", ".htm"):
        from html.parser import HTMLParser

        class _TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self._texts = []
                self._skip = False
            def handle_starttag(self, tag, attrs):
                if tag in ("script", "style"):
                    self._skip = True
            def handle_endtag(self, tag):
                if tag in ("script", "style"):
                    self._skip = False
            def handle_data(self, data):
                if not self._skip:
                    stripped = data.strip()
                    if stripped:
                        self._texts.append(stripped)
            def result(self):
                return "\n\n".join(self._texts)

        extractor = _TextExtractor()
        extractor.feed(path.read_text(encoding="utf-8", errors="replace"))
        return extractor.result()

    if ext == ".zim":
        import zim as zim_mod

        parts = []
        zim_file = zim_mod.open(str(path))
        try:
            for article in zim_file.articles:
                text = article.text if article.text else ""
                title = article.title if article.title else ""
                url = article.url if article.url else ""
                if text.strip():
                    header = f"[{title}]({url})" if title else ""
                    parts.append(f"{header}\n{text}" if header else text)
        finally:
            zim_file.close()
        return "\n\n---\n\n".join(parts) if parts else ""

    return path.read_text(encoding="utf-8", errors="replace")


class LlamaRAGEngine:
    def __init__(self, settings: RAGSettings):
        self._settings = settings
        self._chroma_client: Any = None
        self._collection: Any = None
        self._vector_store: Optional[ChromaVectorStore] = None
        self._index: Optional[VectorStoreIndex] = None
        self._embed_model: Optional[OnnxEmbedding] = None
        self._splitter = SentenceSplitter(
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
        loop = asyncio.get_event_loop()

        def _init():
            os.makedirs(self._settings.vector_store_path, exist_ok=True)
            download_onnx_model(self._settings)
            _load_onnx_session(self._settings.model_dir, device=self._settings.device)

            self._embed_model = OnnxEmbedding(
                model_dir=self._settings.model_dir,
                device=self._settings.device,
                embed_batch_size=self._settings.indexing_batch_size,
            )

            self._chroma_client = chromadb.PersistentClient(
                path=self._settings.vector_store_path,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._chroma_client.get_or_create_collection(
                name="hakeem_rag",
                metadata={"hnsw:space": "cosine"},
            )

            self._vector_store = ChromaVectorStore(
                chroma_collection=self._collection,
            )

            self._index = VectorStoreIndex.from_vector_store(
                vector_store=self._vector_store,
                embed_model=self._embed_model,
            )

        await loop.run_in_executor(None, _init)
        self._initialized = True
        logger.info(
            f"LlamaRAGEngine initialized: model_dir={self._settings.model_dir}/onnx, "
            f"collection={self._collection.count()} chunks"
        )

    async def index_document(
        self, file_path: str, doc_id: Optional[str] = None
    ) -> dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("RAGEngine not initialized")

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        doc_id = doc_id or path.stem
        text = _read_file(path)

        if not text.strip():
            logger.warning(f"Empty file: {file_path}")
            return {
                "doc_id": doc_id,
                "filename": path.name,
                "chunks": 0,
                "status": "empty",
            }

        file_mtime = path.stat().st_mtime

        loop = asyncio.get_event_loop()

        def _index():
            document = Document(
                text=text,
                metadata={
                    "doc_id": doc_id,
                    "filename": path.name,
                    "source_file": str(path.resolve()),
                    "mtime": file_mtime,
                },
            )

            nodes = self._splitter.get_nodes_from_documents([document])

            for i, node in enumerate(nodes):
                node.metadata["chunk_index"] = i
                node.embedding = self._embed_model._get_text_embedding(
                    node.get_content()
                )
                node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
                    node_id=doc_id,
                    node_type=ObjectType.DOCUMENT,
                )

            existing = self._collection.get(where={"doc_id": doc_id})
            if existing["ids"]:
                self._collection.delete(ids=existing["ids"])
            self._vector_store.add(nodes)

            return len(nodes)

        chunk_count = await loop.run_in_executor(None, _index)
        logger.info(f"Indexed {path.name}: {chunk_count} chunks")
        return {
            "doc_id": doc_id,
            "filename": path.name,
            "chunks": chunk_count,
            "status": "indexed",
        }

    async def index_directory(self, directory: str) -> list[dict[str, Any]]:
        if not self._initialized:
            raise RuntimeError("RAGEngine not initialized")

        path = Path(directory)
        if not path.exists():
            logger.warning(f"Directory not found: {directory}")
            return []

        results = []
        for f in sorted(path.rglob("*")):
            if f.is_file() and f.suffix.lower() in _SUPPORTED_EXTENSIONS:
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

        total_chunks = 0

        for d in dirs:
            dpath = Path(d)
            if not dpath.exists():
                logger.warning(f"RAG: source directory not found: {d}")
                continue

            for f in sorted(dpath.rglob("*")):
                if not f.is_file() or f.suffix.lower() not in _SUPPORTED_EXTENSIONS:
                    continue

                doc_id = f.stem
                current_mtime = f.stat().st_mtime
                stored_mtime = existing_mtimes.get(doc_id)
                rel = str(f.resolve().relative_to(Path.cwd().resolve()))

                if doc_id not in existing_mtimes:
                    logger.info(f"RAG: {rel}: NEW -> indexing")
                elif stored_mtime is None or current_mtime > stored_mtime:
                    if stored_mtime is None:
                        logger.info(f"RAG: {rel}: no stored mtime -> re-indexing")
                    else:
                        logger.info(
                            f"RAG: {rel}: mtime CHANGED "
                            f"({stored_mtime} -> {current_mtime}) -> re-indexing"
                        )
                else:
                    logger.debug(f"RAG: {rel}: unchanged -> skipping")
                    continue

                result = await self.index_document(str(f), doc_id=doc_id)
                total_chunks += result.get("chunks", 0)
                delay = self._settings.indexing_delay_ms / 1000
                if delay > 0:
                    await asyncio.sleep(delay)

        logger.info(
            f"RAG: index_if_changed done, {total_chunks} chunks indexed"
        )
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
            retriever = self._index.as_retriever(
                similarity_top_k=top_k,
            )
            return retriever.retrieve(query)

        raw = await loop.run_in_executor(None, _search)
        if not raw:
            return []

        output = []
        for item in raw:
            similarity = item.score if item.score is not None else 0.0
            if similarity < min_score:
                continue
            meta = item.node.metadata or {}
            output.append(
                {
                    "chunk_id": item.node.node_id,
                    "content": item.node.get_content(),
                    "score": similarity,
                    "source_file": meta.get("source_file", ""),
                    "filename": meta.get("filename", ""),
                }
            )
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
            for i, chunk_id in enumerate(all_data["ids"]):
                meta = all_data["metadatas"][i] if all_data["metadatas"] else {}
                did = meta.get("doc_id", chunk_id)
                if did not in seen:
                    seen[did] = {
                        "id": did,
                        "filename": meta.get("filename", ""),
                        "chunks": 0,
                    }
                seen[did]["chunks"] += 1
            return list(seen.values())

        return await loop.run_in_executor(None, _list)


_engine: Optional[LlamaRAGEngine] = None


async def get_rag_engine() -> Optional[LlamaRAGEngine]:
    return _engine


async def init_rag_engine(settings: RAGSettings) -> Optional[LlamaRAGEngine]:
    global _engine
    if not settings.enabled:
        logger.info("RAG is disabled (RAG_ENABLED=false)")
        return None
    engine = LlamaRAGEngine(settings)
    await engine.initialize()
    _engine = engine
    return engine
