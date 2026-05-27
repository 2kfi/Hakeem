# Arkan Fakoseh -  @2kfi on github
import logging
from typing import Optional

from core.app_state import get_app_state
from core.config import get_settings
from core.redis_manager import RedisManager
from core.schemas import MessageRole
from sessions.conversation_store import ConversationStore

logger = logging.getLogger(__name__)


class ConversationSummarizer:
    LOCK_KEY_PREFIX = "conv_summary_lock"

    def __init__(self, redis: RedisManager, conversation_store: ConversationStore):
        self.redis = redis
        self.store = conversation_store
        self._settings = get_settings()

    def _lock_key(self, device_id: str) -> str:
        return f"{self.LOCK_KEY_PREFIX}:{device_id}"

    async def get_summarized_history(self, device_id: str) -> tuple[Optional[str], list[dict[str, str]]]:
        summary = await self.store.get_summary(device_id)
        raw_messages = await self.store.get_history_for_llm(device_id, limit=50)
        return summary, raw_messages

    async def maybe_summarize(self, device_id: str) -> None:
        trigger = self._settings.session.summarize_after
        if trigger <= 0:
            return

        lock_acquired = await self._acquire_lock(device_id)
        if not lock_acquired:
            return

        try:
            await self._do_summarize(device_id, trigger)
        except Exception as e:
            logger.error(f"Summarization failed for {device_id}: {e}", exc_info=True)
        finally:
            await self._release_lock(device_id)

    async def _acquire_lock(self, device_id: str) -> bool:
        locked = await self.redis.client.setnx(self._lock_key(device_id), "1")
        if locked:
            await self.redis.expire(self._lock_key(device_id), 10)
        return locked

    async def _release_lock(self, device_id: str) -> None:
        await self.redis.delete(self._lock_key(device_id))

    async def _do_summarize(self, device_id: str, trigger: int) -> None:
        raw = await self.redis.lrange(self.store.get_key(device_id), 0, -1)

        user_indices = [i for i, item in enumerate(raw) if isinstance(item, dict) and item.get("role") == MessageRole.USER.value]

        if len(user_indices) <= trigger:
            return

        keep = self._settings.session.summarize_keep_last
        trim_idx = user_indices[-keep] if keep > 0 and len(user_indices) >= keep else 0

        if trim_idx <= 0:
            return

        old_msgs = raw[:trim_idx]
        existing_summary = await self.store.get_summary(device_id)
        summary_text = await self._summarize(old_msgs, existing_summary)

        await self.store.set_summary(device_id, summary_text)
        await self.redis.ltrim(self.store._key(device_id), trim_idx, -1)

        logger.info(f"Summarized {len(old_msgs)} old messages for {device_id}")

    async def _summarize(self, messages: list[dict], existing_summary: Optional[str] = None) -> str:
        client = get_app_state().get_llm_client()
        if not client:
            raise RuntimeError("LLM client not initialized")

        convo_lines = []
        for m in messages:
            role = m.get("role", "unknown")
            content = m.get("content", "")
            if content:
                convo_lines.append(f"{role}: {content[:500]}")

        prompt_parts = ["Condense the following conversation into a brief summary that preserves all important facts, user preferences, and context needed for future responses. Keep it concise (2-3 sentences). Preserve the original language of the conversation."]

        if existing_summary:
            prompt_parts.append(f"\nPrevious summary (update with new messages):\n{existing_summary}")

        prompt_parts.append("\nConversation:\n" + "\n".join(convo_lines))
        prompt_parts.append("\n\nSummary:")

        response = await client.chat.completions.create(
            model=self._settings.llm.model,
            messages=[{"role": "user", "content": "\n".join(prompt_parts)}],
            max_tokens=300,
        )
        return response.choices[0].message.content or ""
