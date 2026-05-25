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
