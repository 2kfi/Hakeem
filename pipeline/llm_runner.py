import asyncio
import json
import logging
from typing import Any, Optional

import httpx
from openai import APIError

from core.app_state import get_app_state
from core.config import get_settings
from core.redis_manager import RedisManager
from core.schemas import MessageRole
from sessions.conversation_store import ConversationStore
from sessions.conversation_summarizer import ConversationSummarizer
from tools.router import route_tool_calls_batch

logger = logging.getLogger(__name__)


async def _get_rag_context(user_message: str) -> Optional[str]:
    try:
        from rag.engine import get_rag_engine
        engine = await get_rag_engine()
        if engine and engine.is_initialized:
            results = await engine.search(user_message)
            if results:
                return engine.format_context(results)
    except Exception as e:
        logger.warning(f"RAG retrieval failed: {e}")
    return None


class LLMRunner:
    def __init__(self, redis: RedisManager, conversation_store: ConversationStore):
        self.redis = redis
        self.conversation_store = conversation_store
        self._settings = get_settings()
        self._max_tool_loops = self._settings.mcp.max_tool_loops

    async def run_query(
        self,
        device_id: str,
        user_message: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        client = get_app_state().get_llm_client()
        if not client:
            raise RuntimeError("LLM client not initialized")

        summarizer = ConversationSummarizer(self.redis, self.conversation_store)
        summary, recent = await summarizer.get_summarized_history(device_id)

        rag_context = None
        if self._settings.rag.enabled:
            rag_context = await _get_rag_context(user_message)

        messages = []
        prompt = system_prompt or self._settings.llm.system_prompt
        if prompt:
            messages.append({"role": "system", "content": prompt})
        if rag_context:
            messages.append({"role": "system", "content": f"Relevant documentation:\n{rag_context}"})
        if summary:
            messages.append({"role": "system", "content": f"Conversation so far: {summary}"})
        messages.extend(recent)
        messages.append({"role": "user", "content": user_message})

        tools_schema = await self._get_tools_schema()

        for iteration in range(self._max_tool_loops):
            response = await self._call_llm_with_retry(
                client=client,
                messages=messages,
                tools=tools_schema if tools_schema else None,
            )
            message = response.choices[0].message

            if not message.tool_calls:
                if iteration == 0:
                    await self.conversation_store.add_message(device_id, MessageRole.USER, user_message)
                await self.conversation_store.add_message(device_id, MessageRole.ASSISTANT, message.content or "")
                await summarizer.maybe_summarize(device_id)
                return message.content or ""

            if iteration == 0:
                await self.conversation_store.add_message(device_id, MessageRole.USER, user_message)
            messages.append(message.model_dump(exclude_none=True))

            tool_results = await route_tool_calls_batch(device_id, device_id, [
                tc.model_dump() for tc in message.tool_calls
            ])

            for i, tc_result in enumerate(tool_results):
                tc = message.tool_calls[i]
                tool_name = tc.function.name
                content = json.dumps(tc_result.result) if tc_result.success else f"Error: {tc_result.error}"
                await self.conversation_store.add_tool_result(device_id, tc.id, tool_name, content)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tool_name,
                    "content": content,
                })

        final_response = await self._call_llm_with_retry(
            client=client,
            messages=messages,
        )
        text = final_response.choices[0].message.content or ""
        await self.conversation_store.add_message(device_id, MessageRole.ASSISTANT, text)
        await summarizer.maybe_summarize(device_id)
        return text

    async def _call_llm_with_retry(
        self,
        client: Any,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        max_retries: int = 3,
    ) -> Any:
        last_error = None
        for attempt in range(max_retries):
            try:
                return await client.chat.completions.create(
                    model=self._settings.llm.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto" if tools else None,
                )
            except (APIError, httpx.HTTPError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait = 1.0 * (2 ** attempt)
                    logger.warning(f"LLM API error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait}s")
                    await asyncio.sleep(wait)
        raise last_error

    async def _get_tools_schema(self) -> Optional[list[dict[str, Any]]]:
        from tools.registry import get_tool_registry
        registry = await get_tool_registry()
        tools = registry.get_all()
        return [self._tool_to_schema(t) for t in tools.values()]

    def _tool_to_schema(self, tool) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            },
        }