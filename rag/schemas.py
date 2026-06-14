from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel


class Chunk(BaseModel):
    id: str
    text: str
    metadata: dict[str, Any] = {}
    embedding: Optional[list[float]] = None


class Document(BaseModel):
    id: str
    filename: str
    filepath: str
    chunks: list[Chunk] = []
    created_at: str = ""


class IndexResult(BaseModel):
    doc_id: str
    filename: str
    chunks: int
    status: str


class Entity(BaseModel):
    name: str
    type: str
    domain: str = ""
    metadata: dict[str, Any] = {}


class GraphPath(BaseModel):
    path: list[dict[str, str]]
    score: float = 1.0


class ScoredChunk(BaseModel):
    chunk_id: str
    content: str
    score: float
    source_file: str = ""
    filename: str = ""
    domain: str = ""
    doc_id: str = ""
    parent_chunk_id: str = ""
    parent_text: str = ""
    chunk_index: int = 0


class RAGResponse(BaseModel):
    context: str = ""
    formatted_context: str = ""
    chunks: list[ScoredChunk] = []
    graph_paths: list[GraphPath] = []
    domains: list[str] = []
    citations: list[str] = []
    verification_status: str = ""
    sufficient: bool = True
    error: Optional[str] = None


class CRAGResult(BaseModel):
    sufficient: bool
    status: str
    feedback: str = ""
    score: float = 0.0


class DomainRoute(BaseModel):
    domain: str
    confidence: float
    entities: list[Entity] = []
