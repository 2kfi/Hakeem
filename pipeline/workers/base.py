import asyncio
import json
import logging
import time
from typing import Any, Callable, Optional

from core.config import get_settings
from core.redis_manager import RedisManager

logger = logging.getLogger(__name__)

RETRY_COUNTER_PREFIX = "worker_retry:"
RETRY_COUNTER_TTL = 3600
DLQ_STREAM_SUFFIX = "_dlq"


class BaseWorker:
    def __init__(
        self,
        redis: RedisManager,
        stream: str,
        group: str,
        consumer: str,
        handler: Callable,
        poll_timeout: int = 5000,
        max_retries: int = 3,
        target_stream: Optional[str] = None,
        backoff_base: float = 1.0,
    ):
        self.redis = redis
        self.stream = stream
        self.group = group
        self.consumer = consumer
        self.handler = handler
        self.poll_timeout = poll_timeout
        self.max_retries = max_retries
        self.target_stream = target_stream
        self.backoff_base = backoff_base
        self.dlq_stream = stream + DLQ_STREAM_SUFFIX
        self._running = False
        self._epoch = time.time()

    def _retry_key(self, msg_id: str) -> str:
        return f"{RETRY_COUNTER_PREFIX}{self.stream}:{self._epoch}:{msg_id}"

    async def _get_retry_count(self, msg_id: str) -> int:
        raw = await self.redis.get(self._retry_key(msg_id))
        return int(raw) if raw else 0

    async def _increment_retry_count(self, msg_id: str) -> int:
        key = self._retry_key(msg_id)
        count = await self.redis.client.incr(key)
        await self.redis.client.expire(key, RETRY_COUNTER_TTL)
        return count

    async def _clean_retry_count(self, msg_id: str):
        await self.redis.delete(self._retry_key(msg_id))

    async def _send_to_dlq(self, msg_id: str, data: dict, error: str):
        dlq_entry = {
            "original_stream": self.stream,
            "original_msg_id": msg_id,
            "consumer": self.consumer,
            "data": json.dumps(data, default=str),
            "error": str(error),
        }
        try:
            await self.redis.xadd(self.dlq_stream, dlq_entry, maxlen=1000)
            logger.warning(f"Sent {msg_id} to dead-letter queue {self.dlq_stream}")
        except Exception as dlq_err:
            logger.error(f"Failed to send {msg_id} to DLQ: {dlq_err}")

    async def start(self):
        self._running = True
        await self.redis.xgroup_create(self.stream, self.group)
        logger.info(f"Worker {self.consumer} starting on stream {self.stream}")
        while self._running:
            try:
                result = await self._process_one()
                if result:
                    keys = list(result.keys())
                    logger.debug(f"Worker {self.consumer} got result: keys={keys}")
                    if self.target_stream:
                        await self.redis.xadd(self.target_stream, result, maxlen=1000)
                        logger.info(f"Forwarded to {self.target_stream}: {len(result)} fields")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {self.consumer} error: {e}", exc_info=True)
                await asyncio.sleep(1)

    def stop(self):
        self._running = False

    async def _process_one(self):
        messages = await self.redis.xreadgroup(
            group=self.group,
            consumer=self.consumer,
            streams={self.stream: ">"},
            count=1,
            block=self.poll_timeout,
        )
        if not messages:
            return

        msg = messages[0]
        msg_id = msg["id"]
        data = msg["data"]

        try:
            result = await self.handler(data)
            await self.redis.xack(self.stream, self.group, msg_id)
            await self._clean_retry_count(msg_id)
            return result
        except Exception as e:
            logger.error(f"Handler failed on {msg_id}: {e}")
            delivery_count = await self._increment_retry_count(msg_id)
            if delivery_count >= self.max_retries:
                logger.warning(f"Discarding {msg_id} after {delivery_count} attempts")
                await self._send_to_dlq(msg_id, data, str(e))
                await self.redis.xack(self.stream, self.group, msg_id)
            else:
                backoff_time = self.backoff_base * (2 ** (delivery_count - 1))
                logger.info(f"Retrying {msg_id} after {backoff_time}s (attempt {delivery_count}/{self.max_retries})")
                await asyncio.sleep(backoff_time)
            return None