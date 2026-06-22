import asyncio
import json
import logging
from starlette.websockets import WebSocketState

from core.config import get_settings
from core.redis_manager import RedisManager
from api.websocket import get_active_connection

logger = logging.getLogger(__name__)

WS_SEND_TIMEOUT = 30.0
PENDING_RESPONSE_TTL = 300


async def _cache_pending_response(redis: RedisManager, device_id: str, data: dict) -> None:
    key = f"pending_responses:{device_id}"
    payload = {
        "audio": data.get("audio", ""),
        "text": data.get("text", ""),
        "text_only": data.get("text_only", "false") == "true",
    }
    await redis.client.rpush(key, json.dumps(payload))
    await redis.client.expire(key, PENDING_RESPONSE_TTL)
    logger.info(f"Cached pending response for {device_id} (TTL={PENDING_RESPONSE_TTL}s)")


async def response_handler(data: dict) -> None:
    device_id = data.get("device_id", "")
    ws = get_active_connection(device_id)
    if ws is None or ws.client_state != WebSocketState.CONNECTED:
        redis = await RedisManager.get_instance()
        await _cache_pending_response(redis, device_id, data)
        return

    audio = data.get("audio", "")
    text = data.get("text", "")
    text_only = data.get("text_only", "false") == "true"
    msg = {"type": "audio_chunk", "audio_data": audio, "text": text}
    if text_only:
        msg["text_only"] = True
    try:
        await asyncio.wait_for(ws.send_json(msg), timeout=WS_SEND_TIMEOUT)
        logger.info(f"Sent response to {device_id}")
    except Exception as e:
        logger.error(f"Failed to send to {device_id}: {e}")
        redis = await RedisManager.get_instance()
        await _cache_pending_response(redis, device_id, data)


async def process_responses(redis: RedisManager, consumer: str):
    from pipeline.workers.base import BaseWorker

    settings = get_settings()
    worker = BaseWorker(
        redis=redis,
        stream=settings.pipeline.response_stream,
        group=settings.pipeline.consumer_group,
        consumer=consumer,
        handler=response_handler,
        poll_timeout=settings.pipeline.poll_timeout_ms,
        max_retries=1,
    )
    await worker.start()