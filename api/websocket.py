# Arkan Fakoseh -  @2kfi on github
import asyncio
import base64
import json
import logging
import time
from typing import Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from starlette.websockets import WebSocketState

from core.config import get_settings
from core.jwt_auth import ws_verify
from core.redis_manager import RedisManager, get_redis
from core.schemas import DeviceInfo, DeviceStatus, WSMessage, WSMessageType
from sessions.device_registry import DeviceRegistry
from tools.registry import get_tool_registry
from tools.registry import ToolDefinition
from tools.call_client_tool import get_tool_bridge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["websocket"])

_active_connections: dict[str, WebSocket] = {}
_connection_generation: dict[str, int] = {}
_connection_locks: dict[str, asyncio.Lock] = {}
_locks_lock: asyncio.Lock = asyncio.Lock()
_pubsub_listener_started: bool = False


async def _get_lock(device_id: str) -> asyncio.Lock:
    async with _locks_lock:
        if device_id not in _connection_locks:
            _connection_locks[device_id] = asyncio.Lock()
        return _connection_locks[device_id]


async def _cleanup_lock(device_id: str) -> None:
    async with _locks_lock:
        _connection_locks.pop(device_id, None)


async def _start_ws_listener(node_id: str, redis: RedisManager) -> None:
    global _pubsub_listener_started
    if _pubsub_listener_started:
        logger.warning("WS listener already started, skipping duplicate")
        return
    _pubsub_listener_started = True

    channel = f"hakeem:ws_send:{node_id}"
    reconnect_count = 0
    max_reconnects = 20
    try:
        while reconnect_count <= max_reconnects:
            pubsub = None
            try:
                pubsub = redis.client.pubsub()
                await pubsub.subscribe(channel)
                if reconnect_count > 0:
                    logger.info(f"WS listener reconnected to {channel} (attempt #{reconnect_count})")
                else:
                    logger.info(f"WS listener subscribed to {channel}")
                reconnect_count = 0
                async for msg in pubsub.listen():
                    if msg["type"] == "message":
                        try:
                            data = json.loads(msg["data"])
                            device_id = data.get("device_id")
                            if device_id and device_id in _active_connections:
                                ws = _active_connections[device_id]
                                if ws.client_state == WebSocketState.CONNECTED:
                                    await ws.send_json(data)
                        except json.JSONDecodeError as e:
                            logger.error(f"WS send error: invalid JSON: {e}")
                        except Exception as e:
                            logger.error(f"WS send error: {e}")
            except asyncio.CancelledError:
                logger.info("WS listener cancelled")
                return
            except Exception as e:
                reconnect_count += 1
                if reconnect_count > max_reconnects:
                    logger.critical(f"WS listener gave up after {max_reconnects} attempts: {e}")
                    return
                logger.error(f"WS listener error (attempt #{reconnect_count}): {e}, reconnecting in 5s...")
                await asyncio.sleep(min(5 * reconnect_count, 60))
            finally:
                if pubsub is not None:
                    try:
                        await pubsub.unsubscribe(channel)
                        await pubsub.close()
                    except Exception:
                        pass
    finally:
        _pubsub_listener_started = False


async def _register_phone_tools(device_id: str, capabilities: list[str], tools_list: list[dict], previous_names: set[str] | None = None):
    registry = await get_tool_registry()
    registered_names = set()
    for tool_def in tools_list:
        name = tool_def.get("name", "")
        if name:
            await registry.register_remote_tool(name, ToolDefinition(
                name=name,
                description=tool_def.get("description", ""),
                input_schema=tool_def.get("input_schema", {"type": "object", "properties": {}, "required": []}),
            ), owner_device_id=device_id)
            registered_names.add(name)
            logger.info(f"Registered remote tool [{name}] from device {device_id}")
    if previous_names is not None:
        for old_name in previous_names - registered_names:
            await registry.remove_remote_tool(old_name)
            logger.info(f"Unregistered stale remote tool [{old_name}] from device {device_id}")
    return registered_names


@router.websocket("/connect")
async def ws_connect(websocket: WebSocket, token: Optional[str] = Query(None)):
    if get_settings().auth.disabled:
        claims = {"device_id": "anon", "user_id": "anon", "permissions": ["*"]}
        await websocket.accept()
    else:
        if not token:
            await websocket.close(code=4001, reason="Missing token")
            return

        try:
            claims = await ws_verify(token)
        except Exception as e:
            await websocket.close(code=4002, reason=f"Invalid token: {e}")
            return

        await websocket.accept()

    device_id = claims.get("device_id")
    user_id = claims.get("user_id")

    settings = get_settings()
    redis = await get_redis()
    device_registry = DeviceRegistry(redis)

    capabilities = []
    remote_tools = []
    try:
        caps_raw = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        if caps_raw.get("type") == "connect":
            capabilities = caps_raw.get("capabilities", [])
            remote_tools = caps_raw.get("tools", [])
            logger.info(f"Device {device_id} connected with capabilities: {capabilities}, tools: {len(remote_tools)}")
    except asyncio.TimeoutError:
        logger.warning(f"Device {device_id} did not send connect message within 10s")
    except Exception as e:
        logger.warning(f"Failed to parse connect message from {device_id}: {e}")

    connection_gen = _connection_generation.get(device_id, 0) + 1
    _connection_generation[device_id] = connection_gen

    prev_tool_names = set()
    registry = await get_tool_registry()

    device_info = DeviceInfo(
        device_id=device_id,
        user_id=user_id,
        capabilities=capabilities,
        status=DeviceStatus.ONLINE,
        node_id=settings.cluster.node_id,
    )
    await device_registry.register(device_id, device_info)

    all_tools = []
    for cap in capabilities:
        all_tools.append({"name": cap, "description": f"Remote tool: {cap}", "input_schema": {"type": "object", "properties": {}, "required": []}})
    all_tools.extend(remote_tools)

    prev_tool_names = await _register_phone_tools(device_id, capabilities, all_tools)

    async with await _get_lock(device_id):
        existing = _active_connections.get(device_id)
        if existing is not None and existing.client_state == WebSocketState.CONNECTED:
            logger.warning(f"Device {device_id} already has an active connection, closing old one")
            try:
                await existing.close(code=1000, reason="Replaced by new connection")
            except Exception:
                pass
        _active_connections[device_id] = websocket

    await websocket.send_json({
        "type": "connected",
        "device_id": device_id,
        "node_id": settings.cluster.node_id,
    })

    pending_key = f"pending_response:{device_id}"
    pending_raw = await redis.get(pending_key)
    if pending_raw:
        try:
            if isinstance(pending_raw, str):
                pending_msg = json.loads(pending_raw)
            else:
                pending_msg = pending_raw
            await websocket.send_json({
                "type": "audio_chunk",
                "audio_data": pending_msg.get("audio", ""),
                "text": pending_msg.get("text", ""),
                "text_only": pending_msg.get("text_only", False),
            })
            logger.info(f"Delivered cached pending response to reconnected device {device_id}")
        except Exception as e:
            logger.warning(f"Failed to deliver cached response for {device_id}: {e}")
        await redis.delete(pending_key)

    try:
        heartbeat_missed = 0
        max_heartbeat_misses = 3
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=settings.session.heartbeat_interval * 2,
                )
                heartbeat_missed = 0
            except asyncio.TimeoutError:
                heartbeat_missed += 1
                if heartbeat_missed >= max_heartbeat_misses:
                    logger.warning(f"Device {device_id} missed {max_heartbeat_misses} heartbeats, disconnecting")
                    await websocket.close(code=4004, reason="Heartbeat timeout")
                    break
                await websocket.send_json({"type": "heartbeat", "timestamp": time.time()})
                await device_registry.heartbeat(device_id)
                continue

            msg_type = data.get("type")
            if msg_type == "heartbeat":
                await device_registry.heartbeat(device_id)
                await websocket.send_json({"type": "heartbeat_ack", "timestamp": data.get("timestamp")})

            elif msg_type == "heartbeat_ack":
                await device_registry.heartbeat(device_id)

            elif msg_type == "tool_response":
                correlation_id = data.get("correlation_id")
                result = data.get("result")
                error = data.get("error")
                bridge = await get_tool_bridge()
                await bridge.handle_response(correlation_id, result, error)

            elif msg_type == "disconnect":
                break

            elif msg_type == "audio":
                await _handle_audio(websocket, device_id, data, redis)

            elif msg_type == "tools_update":
                tools_list = data.get("tools", [])
                tool_names = await _register_phone_tools(device_id, [], tools_list, previous_names=prev_tool_names)
                prev_tool_names = tool_names
                await websocket.send_json({"type": "tools_updated", "count": len(tools_list)})

            elif msg_type == "text":
                user_text = data.get("text", "")
                if not user_text:
                    await websocket.send_json({"type": "error", "message": "Missing text"})
                    continue
                await redis.xadd(settings.pipeline.llm_stream, {
                    "device_id": device_id,
                    "session_id": device_id,
                    "text": user_text,
                    "language": data.get("language", ""),
                    "skip_tts": data.get("skip_tts", "false"),
                }, maxlen=1000)
                await websocket.send_json({"type": "accepted", "message": "Text processing started"})

            else:
                await websocket.send_json({"type": "error", "message": f"Unknown type: {msg_type}"})

    except WebSocketDisconnect:
        logger.info(f"Device {device_id} disconnected")
    except Exception as e:
        logger.error(f"WS error for device {device_id}: {e}", exc_info=True)
    finally:
        if _connection_generation.get(device_id) == connection_gen:
            async with await _get_lock(device_id):
                _active_connections.pop(device_id, None)
                _connection_generation.pop(device_id, None)
            await _cleanup_lock(device_id)
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.close(code=1000, reason="Connection closed")
            except Exception as e:
                logger.debug(f"WS close error for {device_id}: {e}")
            await device_registry.set_status(device_id, DeviceStatus.OFFLINE)
            await device_registry.unregister(device_id)
            n = await registry.remove_device_tools(device_id)
            if n:
                logger.info(f"Unregistered {n} remote tools for disconnected device {device_id}")


async def _handle_audio(websocket: WebSocket, device_id: str, data: dict, redis: RedisManager) -> None:
    audio_b64 = data.get("audio_data") or data.get("data", "")
    if not audio_b64:
        await websocket.send_json({"type": "error", "message": "Missing audio_data"})
        return

    settings = get_settings()

    content_type = data.get("content_type", "audio/wav")
    if content_type not in settings.allowed_audio_types:
        await websocket.send_json({
            "type": "error",
            "message": f"Unsupported audio type: {content_type} (allowed: {settings.allowed_audio_types})"
        })
        return

    try:
        audio_bytes = base64.b64decode(audio_b64)
        audio_size_mb = len(audio_bytes) / (1024 * 1024)
        if audio_size_mb > settings.max_audio_size_mb:
            await websocket.send_json({
                "type": "error",
                "message": f"Audio too large: {audio_size_mb:.2f}MB (max: {settings.max_audio_size_mb}MB)"
            })
            return
    except Exception as e:
        await websocket.send_json({"type": "error", "message": f"Invalid audio data: {e}"})
        return

    stream_key = settings.pipeline.stt_stream

    await redis.xadd(stream_key, {
        "device_id": device_id,
        "session_id": device_id,
        "audio_data": audio_b64,
        "language": data.get("language", ""),
        "task": data.get("task") or "transcribe",
        "skip_tts": data.get("skip_tts", "false"),
    }, maxlen=1000)

    await websocket.send_json({
        "type": "accepted",
        "message": "Processing started",
    })


def get_active_connection(device_id: str) -> Optional[WebSocket]:
    return _active_connections.get(device_id)


