import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.params import Query

from core.jwt_auth import verify_jwt
from rag.engine import get_rag_engine, HakeemRAGEngine
from rag.schemas import Document, IndexResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


async def _get_engine() -> HakeemRAGEngine:
    engine = await get_rag_engine()
    if not engine or not engine.is_initialized:
        raise HTTPException(status_code=503, detail="RAG engine not available")
    return engine


@router.get("/documents")
async def list_documents(
    domain: Optional[str] = Query(None),
    _=Depends(verify_jwt),
):
    engine = await _get_engine()
    docs = await engine.list_documents()
    if domain:
        docs = [d for d in docs if d.get("domain") == domain]
    logger.info("List documents (domain=%s): %d docs", domain or "all", len(docs))
    return {"documents": docs}


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    domain: str = Query(..., description="Target domain (hepatology/nephrology/neurology)"),
    _=Depends(verify_jwt),
):
    engine = await _get_engine()
    if domain not in engine._settings.domains:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid domain '{domain}'. Valid: {engine._settings.domains}",
        )

    tmp_dir = Path("/tmp/hakeem_rag_uploads")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / file.filename

    content = await file.read()
    tmp_path.write_bytes(content)

    try:
        result = await engine.index_document(str(tmp_path), domain)
        logger.info("Uploaded %s -> domain=%s: doc_id=%s, chunks=%d",
                     file.filename, domain, result.get("doc_id"), result.get("chunks", 0))
        return result
    finally:
        tmp_path.unlink(missing_ok=True)


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    domain: str = Query(..., description="Domain of the document"),
    _=Depends(verify_jwt),
):
    engine = await _get_engine()
    success = await engine.delete_document(domain, doc_id)
    if not success:
        logger.warning("Delete failed: doc_id=%s not found in domain=%s", doc_id, domain)
        raise HTTPException(status_code=404, detail="Document not found")
    logger.info("Deleted doc_id=%s from domain=%s", doc_id, domain)
    return {"status": "deleted", "doc_id": doc_id}


@router.get("/documents/search")
async def search_documents(
    q: str = Query(..., min_length=1),
    _=Depends(verify_jwt),
):
    engine = await _get_engine()
    result = await engine.query(q)
    logger.info("Search q=%s: domains=%s, chunks=%d, sufficient=%s, verification=%s",
                 q, result.domains, len(result.chunks), result.sufficient, result.verification_status)
    return {
        "query": q,
        "domains": result.domains,
        "results": [
            {
                "doc_id": c.doc_id,
                "filename": c.filename,
                "content": c.content[:500],
                "score": round(c.score, 4),
                "domain": c.domain,
            }
            for c in result.chunks[:10]
        ],
        "sufficient": result.sufficient,
        "verification": result.verification_status,
        "citations": result.citations,
    }


@router.post("/documents/reindex")
async def reindex_documents(_=Depends(verify_jwt)):
    engine = await _get_engine()
    dirs = engine._settings.domain_source_dirs
    logger.info("Reindex triggered for %d domains", len(dirs))
    n = await engine.index_if_changed(dirs)
    logger.info("Reindex done: %d chunks indexed", n)
    return {"status": "reindexed", "chunks_indexed": n}
