# Arkan Fakoseh -  @2kfi on github
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from core.config import get_settings
from core.jwt_auth import verify_jwt
from core.redis_manager import RedisManager, get_redis
from core.schemas import DocumentResponse, SearchResponse, SearchResult

from .engine import get_rag_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

UPLOAD_DIR = Path("./data/documents")


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    token: dict = Depends(verify_jwt),
):
    engine = await get_rag_engine()
    if not engine or not engine.is_initialized:
        raise HTTPException(status_code=503, detail="RAG engine not available")
    docs = await engine.list_documents()
    return [DocumentResponse(**d) for d in docs]


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    token: dict = Depends(verify_jwt),
):
    engine = await get_rag_engine()
    if not engine or not engine.is_initialized:
        raise HTTPException(status_code=503, detail="RAG engine not available")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    supported = {".md", ".txt", ".yaml", ".yml", ".json", ".py", ".cfg", ".ini"}
    ext = Path(file.filename).suffix.lower()
    if ext not in supported:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {', '.join(sorted(supported))}",
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    save_path = UPLOAD_DIR / file.filename

    content = await file.read()
    save_path.write_bytes(content)

    doc_id = Path(file.filename).stem
    try:
        result = await engine.index_document(str(save_path), doc_id=doc_id)
        return DocumentResponse(
            id=result["doc_id"],
            filename=result["filename"],
            status=result["status"],
            chunks=result["chunks"],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        if save_path.exists():
            save_path.unlink()
        raise HTTPException(status_code=500, detail=f"Indexing failed: {e}")


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: str,
    token: dict = Depends(verify_jwt),
):
    engine = await get_rag_engine()
    if not engine or not engine.is_initialized:
        raise HTTPException(status_code=503, detail="RAG engine not available")

    deleted = await engine.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")


@router.get("/search", response_model=SearchResponse)
async def search_documents(
    q: str = Query(..., min_length=1),
    top_k: int = Query(3, ge=1, le=20),
    token: dict = Depends(verify_jwt),
):
    engine = await get_rag_engine()
    if not engine or not engine.is_initialized:
        raise HTTPException(status_code=503, detail="RAG engine not available")

    results = await engine.search(q, top_k=top_k)
    return SearchResponse(
        query=q,
        results=[
            SearchResult(
                chunk_id=r["chunk_id"],
                content=r["content"],
                score=round(r["score"], 4),
                source_file=r["source_file"],
            )
            for r in results
        ],
    )


@router.post("/reindex", response_model=dict)
async def reindex(
    token: dict = Depends(verify_jwt),
):
    engine = await get_rag_engine()
    if not engine or not engine.is_initialized:
        raise HTTPException(status_code=503, detail="RAG engine not available")

    dirs_to_index = get_settings().rag.source_directories or ["./docs"]
    total = 0
    for d in dirs_to_index:
        results = await engine.index_directory(d)
        total += len(results)
    return {"status": "ok", "files_indexed": total}
