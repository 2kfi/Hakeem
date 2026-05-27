# Arkan Fakoseh -  @2kfi on github
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from core.config import get_settings
from core.jwt_auth import verify_jwt
from core.redis_manager import RedisManager
from pipeline.llm_runner import LLMRunner
from rag.engine import get_rag_engine
from sessions.conversation_store import ConversationStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")
_security = HTTPBearer(auto_error=False)


class ChatRequest(BaseModel):
    text: str
    system_prompt: Optional[str] = None
    tools_enabled: bool = True
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    rag: bool = False


class ChatResponse(BaseModel):
    response: str
    rag_used: bool = False
    chunks: int = 0
    model: str = ""


async def _optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
):
    if get_settings().auth.disabled:
        return {"user_id": "anonymous", "device_id": "benchmark"}
    return await verify_jwt(credentials)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    auth: dict = Depends(_optional_auth),
):
    redis = await RedisManager.get_instance()
    conv_store = ConversationStore(redis)
    runner = LLMRunner(redis, conv_store)

    rag_context = None
    chunks = 0
    if body.rag:
        engine = await get_rag_engine()
        if engine and engine.is_initialized:
            results = await engine.search(body.text)
            if results:
                rag_context = engine.format_context(results)
                chunks = len(results)

    response = await runner.run_query(
        device_id=auth.get("device_id", "chat"),
        user_message=body.text,
        system_prompt=body.system_prompt,
        rag_context=rag_context,
        tools_enabled=body.tools_enabled,
        api_base_url=body.api_base_url,
        api_key=body.api_key,
        model=body.model,
    )

    return ChatResponse(
        response=response,
        rag_used=bool(rag_context),
        chunks=chunks,
        model=get_settings().llm.model,
    )
